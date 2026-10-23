"""Orquestração de quatro chamadas internas reais; relatórios só com resultados."""
import csv
import io


def cdr_matches(text, *, tenant, caller, target, unique_id):
    rows = list(csv.reader(io.StringIO(text)))
    selected = [row for row in rows if len(row) >= 17 and row[16] == unique_id]
    if len(selected) != 1:
        return False
    row = selected[0]
    return (row[0] == tenant and row[1] == caller and row[2] == target
            and row[3] == tenant+'-internal' and row[14] == 'ANSWERED'
            and row[13].isdigit() and int(row[13]) >= 1)

import json
from pathlib import Path
import re
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack

from .asterisk_lab import command, cli, load_file
from .call_peer import CallPeer
from .srtp_media import SrtpMedia


def provision_call_endpoints(root, source, prepared):
    """Usa exclusivamente o gerador versionado; arquivos novos também ficam 0600."""
    helper = prepared['conf'].parent/'helpers/conf_generator.py'
    helper.write_text(command(['git','-C',str(root),'show',source+':admin-api/conf_generator.py']).stdout)
    helper.chmod(0o600)
    generator = load_file('lab_call_conf_generator', helper)
    rows = []
    for tenant in ('t1','t2'):
        for number in ('1201','1202'):
            name = tenant+'-'+number
            password = secrets.token_urlsafe(32)
            prepared['credentials'][name] = password
            rows.append({'tenant':tenant,'number':number,'name':name,'display_name':'AXE lab '+number,
                         'password':password,'voicemail_pin':str(100000+secrets.randbelow(900000))})
    for filename, text in generator.render_all(rows).items():
        path = prepared['conf']/'generated'/filename
        path.write_text(text)
        path.chmod(0o600)
    cdr = prepared['conf']/'cdr.conf'
    cdr.write_text(cdr.read_text()+'\n[csv]\nusegmtime=yes\nloguniqueid=yes\nloguserfield=yes\naccountlogs=no\n')
    cdr.chmod(0o600)


def active_unique_id(text, *, tenant, caller, target):
    selected = []
    for line in text.splitlines():
        row = line.split('!')
        if (len(row) == 13 and row[0].startswith('PJSIP/'+tenant+'-'+caller+'-')
                and row[1] == tenant+'-internal' and row[2] == target
                and row[4] == 'Up' and row[8] == tenant
                and re.fullmatch(r'[0-9]+\.[0-9]+',row[12])):
            selected.append(row[12])
    return selected[0] if len(selected) == 1 else None


def recordings(container):
    script = '''import glob,json,os,wave
result={}
for path in glob.glob('/var/spool/asterisk/monitor/*.wav'):
    try:
        with wave.open(path,'rb') as f:
            result[os.path.basename(path)]={'frames':f.getnframes(),'rate':f.getframerate(),'channels':f.getnchannels()}
    except (OSError,EOFError,wave.Error):
        pass
print(json.dumps(result))
'''
    return json.loads(command(['docker','exec',container,'python3','-c',script]).stdout)


def run_one(container, prepared, tenant, caller, target, report):
    prefix = tenant+':'+caller+'-'+target
    checks = report['checks']
    report['phase'] = prefix+':register'
    with ExitStack() as stack:
        a = CallPeer('127.0.0.1',5061,prepared['ca'],tenant+'-'+caller,prepared['credentials'][tenant+'-'+caller])
        stack.callback(a.close)
        b = CallPeer('127.0.0.1',5061,prepared['ca'],tenant+'-'+target,prepared['credentials'][tenant+'-'+target])
        stack.callback(b.close)
        ma, mb = SrtpMedia(b'\x55'*160), SrtpMedia(b'\xaa'*160)
        stack.callback(ma.close)
        stack.callback(mb.close)
        checks[prefix+':register_caller'] = a.register() == 200
        checks[prefix+':register_callee'] = b.register() == 200
        before = set(recordings(container))
        gate = threading.Barrier(2)
        def callee():
            answered = b.answer(mb)
            stats = mb.exchange(b'\x55'*160,gate)
            finished = b.wait_for_bye()
            return answered,stats,finished
        with ThreadPoolExecutor(max_workers=1) as pool:
            other = pool.submit(callee)
            try:
                report['phase'] = prefix+':invite'
                invited = a.invite(target,ma)
                uid = None
                for _ in range(20):
                    uid = active_unique_id(cli(container,'core show channels concise'),
                                           tenant=tenant,caller=caller,target=target)
                    if uid:
                        break
                    time.sleep(0.1)
                if uid is None:
                    raise ValueError('canal ativo único da chamada não foi localizado')
                report['phase'] = prefix+':media'
                stats_a = ma.exchange(b'\xaa'*160,gate)
                report['phase'] = prefix+':bye'
                ended = a.hangup()
                answered, stats_b, bye = other.result(timeout=15)
            finally:
                gate.abort()
        checks[prefix+':established'] = invited and answered
        checks[prefix+':rtp_two_way'] = stats_a['success'] and stats_b['success']
        checks[prefix+':srtp_sdes'] = all(
            stats['encrypted_wire'] and stats['wrong_key_rejected'] for stats in (stats_a,stats_b))
        checks[prefix+':bye'] = ended and bye
        report['media'][prefix] = {'caller':stats_a,'callee':stats_b}
        report['phase'] = prefix+':cdr'
        for _ in range(40):
            result = command(['docker','exec',container,'cat','/var/log/asterisk/cdr-csv/Master.csv'],check=False)
            if cdr_matches(result.stdout,tenant=tenant,caller=caller,target=target,unique_id=uid):
                checks[prefix+':cdr'] = True
                break
            time.sleep(0.1)
        report['phase'] = prefix+':recording'
        for _ in range(30):
            after = recordings(container)
            fresh = [data for name,data in after.items() if name not in before]
            if any(data['frames'] >= 6400 and data['rate'] == 8000 and data['channels'] in (1,2) for data in fresh):
                checks[prefix+':recording'] = True
                break
            time.sleep(0.1)
        # Desregistro usa o diálogo REGISTER original, separado do diálogo da chamada.
        if a.register(expires=0) != 200 or b.register(expires=0) != 200:
            raise ValueError('desregistro após chamada não foi confirmado')


def exercise_calls(container, prepared, report):
    checks = {}
    for tenant in ('t1','t2'):
        for caller,target in (('1202','1201'),('1201','1202')):
            for name in ('register_caller','register_callee','established','rtp_two_way','srtp_sdes','bye','cdr','recording'):
                checks[tenant+':'+caller+'-'+target+':'+name] = False
    checks['no_active_channels'] = False
    report.update(kind='real_internal_calls_sdes_srtp',checks=checks,media={},dtls_tested=False,
                  wss_session_tested=False,operational_go_authorized=False)
    report['cdr_backend_loaded'] = 'cdr_csv.so' in cli(container,'module show like cdr_csv.so')
    try:
        for tenant in ('t1','t2'):
            for caller,target in (('1202','1201'),('1201','1202')):
                run_one(container,prepared,tenant,caller,target,report)
        channels = cli(container,'core show channels count')
        checks['no_active_channels'] = bool(re.search(r'(?m)^0 active channels\s*$',channels))
    except Exception as exc:
        # Dados do SDP, credenciais e strings de exceção não entram no relatório público.
        report['error_type'] = type(exc).__name__
    report.update(passed=sum(value is True for value in checks.values()),total=len(checks))
    report['success'] = report['passed'] == 33 and report['total'] == 33
    return report['success']
