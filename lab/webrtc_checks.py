"""Aceite de WebRTC real: contrato fechado, ativos Git e evidência sanitizada."""
import base64
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import signal
import subprocess
import tarfile
import time

from .call_checks import cdr_rows,cdr_fields
from .wss_probe import probe_wss,untrusted_wss_rejected

TENANTS=('t1','t2','t3')
DIRECTIONS=('forward','reverse')
METRICS=('register','established','dtls','srtp','rtp','tone','audio_attached','ended')
CIPHERS={'AES_CM_128_HMAC_SHA1_80','AEAD_AES_128_GCM','AEAD_AES_256_GCM'}


def browser_checks():
    names={f'webrtc_{metric}:{tenant}:{direction}' for metric in METRICS for tenant in TENANTS for direction in DIRECTIONS}
    names.update('webrtc_unregistered:'+tenant for tenant in TENANTS)
    names.update('webrtc_'+name for name in ('bundle','browser_closed','https_closed','no_page_errors'))
    return names


def required_webrtc_checks():
    return browser_checks() | {'webrtc_wss_ca','webrtc_untrusted_ca_rejected','webrtc_assets_from_git','webrtc_channels_cleared'} | {
        f'webrtc_cdr:{tenant}:{direction}' for tenant in TENANTS for direction in DIRECTIONS} | {
        'webrtc_contacts_cleared:'+tenant for tenant in TENANTS}


def validate_browser_report(report):
    allowed={'schema_version','success','checks','cases','browser_version','phase'}
    if (not isinstance(report,dict) or set(report)-allowed or report.get('schema_version')!=1
            or report.get('success') is not True or not isinstance(report.get('checks'),dict)
            or set(report['checks'])!=browser_checks() or not all(value is True for value in report['checks'].values())
            or not isinstance(report.get('browser_version'),str)
            or not re.fullmatch(r'(?:Chrome|Chromium)/[0-9.]{3,50}',report['browser_version'])):
        raise ValueError('relatório WebRTC inválido')
    if 'phase' in report and not re.fullmatch(r'[a-z_]+(?::t[123]:(?:forward|reverse))?',str(report['phase'])):
        raise ValueError('fase WebRTC inválida')
    cases=report.get('cases')
    if not isinstance(cases,list) or len(cases)!=6: raise ValueError('cenários WebRTC incompletos')
    seen=set()
    proof_keys={'dtls','srtp','rtp','cipher','packets_sent','packets_received','peak_hz','rms','audio_attached','local_ice'}
    for case in cases:
        if not isinstance(case,dict) or set(case)!={'tenant','direction','left','right'}: raise ValueError('cenário WebRTC inválido')
        identity=(case['tenant'],case['direction'])
        if identity in seen or identity[0] not in TENANTS or identity[1] not in DIRECTIONS: raise ValueError('cenário WebRTC duplicado')
        seen.add(identity)
        for side,expected_tone in (('left',880),('right',440)):
            proof=case[side]
            if not isinstance(proof,dict) or set(proof)!=proof_keys: raise ValueError('prova de mídia inválida')
            if any(proof[key] is not True for key in ('dtls','srtp','rtp','audio_attached','local_ice')) or proof['cipher'] not in CIPHERS:
                raise ValueError('mídia WebRTC não comprovada')
            if any(type(proof[key]) is not int or not 25<=proof[key]<=10**9 for key in ('packets_sent','packets_received')):
                raise ValueError('contadores RTP inválidos')
            if any(type(proof[key]) not in (int,float) or not math.isfinite(proof[key]) for key in ('peak_hz','rms')):
                raise ValueError('tom recebido inválido')
            if abs(proof['peak_hz']-expected_tone)>=70 or not 0.015<proof['rms']<=1:
                raise ValueError('tom remoto não comprovado')
    return report


def webrtc_cdr_matches(raw,tenant,source,destination):
    operators={'1010':'recepcao','1011':'recepcao-2'}
    if tenant not in TENANTS or source not in operators or destination not in operators: return False
    rows=cdr_rows(raw)
    if rows is None: return False
    for row in rows:
        fields=cdr_fields(row,tenant,source,destination)
        fields['origin_channel']=bool(re.fullmatch(r'PJSIP/'+tenant+'-'+operators[source]+r'-[0-9a-f]+',row[4]))
        fields['destination_channel']=bool(re.fullmatch(r'PJSIP/'+tenant+'-'+operators[destination]+r'-[0-9a-f]+',row[5]))
        if all(fields.values()): return True
    return False


def prepare_webrtc(root,prepared,source):
    from .asterisk_lab import command
    stage=prepared['conf'].parent
    archive=subprocess.run(['git','-C',str(root),'archive','--format=tar',source,'webphone'],capture_output=True,timeout=30)
    if archive.returncode: raise RuntimeError('ativos WebRTC indisponíveis')
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as exported:
        members=exported.getmembers()
        for member in members:
            parts=PurePosixPath(member.name).parts
            if not parts or parts[0]!='webphone' or '..' in parts or not (member.isdir() or member.isfile()):
                raise ValueError('ativo WebRTC inseguro')
        exported.extractall(stage,members=members,filter='data')
    for item in (stage/'webphone').rglob('*'): item.chmod(0o700 if item.is_dir() else 0o600)
    public=subprocess.run(['openssl','x509','-in',str(prepared['ca']),'-pubkey','-noout'],capture_output=True,timeout=10)
    if public.returncode: raise RuntimeError('chave pública TLS indisponível')
    der=subprocess.run(['openssl','pkey','-pubin','-outform','DER'],input=public.stdout,capture_output=True,timeout=10)
    if der.returncode: raise RuntimeError('chave pública TLS inválida')
    config={'web_root':str(stage/'webphone'),'cert':str(prepared['ca']),
            'key':str(prepared['conf']/'certs/asterisk.key'),'wss_url':'wss://127.0.0.1:8089/ws',
            'spki':base64.b64encode(hashlib.sha256(der.stdout).digest()).decode(),
            'credentials':{tenant+operator:prepared['credentials'][tenant+operator]
                           for tenant in TENANTS for operator in ('-recepcao','-recepcao-2')}}
    target=stage/'browser-input.json'
    with os.fdopen(os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as handle: json.dump(config,handle)
    prepared.update(webrtc_input=target,webrtc_source=source)


def run_browser(root,input_file,output_file):
    with subprocess.Popen(['node',str(Path(root)/'lab/webrtc_browser.cjs'),str(input_file),str(output_file)],
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True) as process:
        try: process.communicate(timeout=160)
        except subprocess.TimeoutExpired:
            try: os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError: pass
            process.communicate(timeout=5)
            raise RuntimeError('prazo WebRTC excedido') from None
        return process.returncode


def exercise_webrtc(root,container,prepared,report):
    from .asterisk_lab import cli,command
    checks=report['checks']
    checks.update({name:False for name in required_webrtc_checks()})
    checks['webrtc_assets_from_git']=prepared.get('webrtc_source')==report['source_commit']
    report['phase']='webrtc_certificate'
    report['wss_tls_version']=probe_wss(prepared['ca'])
    checks['webrtc_wss_ca']=True
    checks['webrtc_untrusted_ca_rejected']=untrusted_wss_rejected()
    command(['docker','exec',container,'mkdir','-p','/var/spool/asterisk/monitor'])
    report['phase']='webrtc_browser'
    output=prepared['conf'].parent/'browser-output.json'
    code=run_browser(root,prepared['webrtc_input'],output)
    if output.is_symlink() or not output.is_file() or output.stat().st_size>65536:
        raise RuntimeError('relatório WebRTC ausente')
    child=json.loads(output.read_text())
    if isinstance(child,dict):
        for name,value in child.get('checks',{}).items():
            if name in browser_checks(): checks[name]=value is True
        phase=child.get('phase')
        if isinstance(phase,str) and re.fullmatch(r'[a-z_]+(?::t[123]:(?:forward|reverse))?',phase): report['webrtc_phase']=phase
    if code: raise RuntimeError('laboratório WebRTC reprovado')
    validated=validate_browser_report(child)
    report['browser_version']=validated['browser_version']
    report['webrtc_cases']=validated['cases']
    report['phase']='webrtc_cdr'
    deadline=time.monotonic()+8
    while time.monotonic()<deadline:
        cdr=command(['docker','exec',container,'cat','/var/log/asterisk/cdr-custom/Lab.csv'],check=False)
        for tenant in TENANTS:
            for direction in DIRECTIONS:
                source,destination=('1010','1011') if direction=='forward' else ('1011','1010')
                checks[f'webrtc_cdr:{tenant}:{direction}']=cdr.returncode==0 and webrtc_cdr_matches(cdr.stdout,tenant,source,destination)
        if all(checks[f'webrtc_cdr:{tenant}:{direction}'] for tenant in TENANTS for direction in DIRECTIONS): break
        time.sleep(0.2)
    active=cli(container,'core show channels concise')
    checks['webrtc_channels_cleared']=not any(line.startswith('PJSIP/') for line in active.splitlines())
    contacts=cli(container,'pjsip show contacts')
    for tenant in TENANTS: checks['webrtc_contacts_cleared:'+tenant]=tenant+'-recepcao' not in contacts
    report.update(dtls_tested=True,wss_session_tested=True)
