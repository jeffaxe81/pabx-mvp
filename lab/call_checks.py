"""Preparação e aceites de chamadas reais; saída pública contém só métricas."""
from concurrent.futures import ThreadPoolExecutor
import csv
from contextlib import ExitStack
import io
from pathlib import Path
import re
import secrets
import time

from .sip_calls import CallPeer
from .srtp_media import SrtpMedia, exchange

TENANTS = ('t1', 't2', 't3')
DIRECTIONS = ('forward', 'reverse')
CHECKS = ('call_register', 'call_established', 'srtp', 'tamper_rejected',
          'replay_rejected', 'hangup', 'channels_cleared', 'cdr')


def required_call_checks():
    return {f'{check}:{tenant}:{direction}' for check in CHECKS
            for tenant in TENANTS for direction in DIRECTIONS}


def prepare_calls(root, prepared, source_commit):
    from .asterisk_lab import command, load_file
    conf = prepared['conf']
    helper = conf.parent/'helpers/conf_generator.py'
    helper.write_text(command(['git','-C',str(root),'show',source_commit+':admin-api/conf_generator.py']).stdout)
    helper.chmod(0o600)
    generator = load_file('lab_conf_generator', helper)
    extensions = []
    for tenant, number in (('t2','1002'), ('t3','1001'), ('t3','1002')):
        name = tenant+'-'+number
        password = secrets.token_urlsafe(32)
        prepared['credentials'][name] = password
        extensions.append({'name':name, 'number':number, 'tenant':tenant,
                           'password':password, 'display_name':'Private Lab '+number,
                           'voicemail_pin':str(secrets.randbelow(90000000)+10000000)})
    for filename, body in generator.render_all(extensions, tenant_ids=TENANTS).items():
        target = conf/'generated'/filename
        target.write_text(body)
        target.chmod(0o600)
    fields = ('accountcode','src','dst','dcontext','channel','dstchannel','disposition','billsec','uniqueid')
    cdr = conf/'cdr_custom.conf'
    cdr.write_text('[mappings]\nLab.csv => '+','.join(
        '${CSV_QUOTE(${CDR('+field+')})}' for field in fields)+'\n')
    cdr.chmod(0o600)


def cdr_rows(raw):
    if not isinstance(raw, str) or len(raw) > 1024*1024:
        return None
    try:
        rows = list(csv.reader(io.StringIO(raw), strict=True))
    except csv.Error:
        return None
    if any(len(row) != 9 for row in rows):
        return None
    return rows


def cdr_fields(row, tenant, source, destination):
    return {'tenant':row[0] == tenant, 'source':row[1] == source,
            'destination':row[2] == destination, 'context':row[3] == tenant+'-internal',
            'origin_channel':re.fullmatch(r'PJSIP/'+re.escape(tenant+'-'+source)+r'-[0-9a-f]+',row[4]) is not None,
            'destination_channel':re.fullmatch(r'PJSIP/'+re.escape(tenant+'-'+destination)+r'-[0-9a-f]+',row[5]) is not None,
            'answered':row[6] == 'ANSWERED',
            'duration':row[7].isdigit() and int(row[7]) >= 1,
            'uniqueid':re.fullmatch(r'[0-9]+\.[0-9]+', row[8]) is not None}


def cdr_matches(raw, tenant, source, destination):
    """Todos os campos devem coincidir no mesmo registro, nunca entre registros."""
    rows = cdr_rows(raw)
    return rows is not None and any(all(cdr_fields(row,tenant,source,destination).values()) for row in rows)


def cdr_diagnostics(raw, tenant, source, destination):
    rows = cdr_rows(raw)
    details = [cdr_fields(row,tenant,source,destination) for row in rows or []]
    names = ('tenant','source','destination','context','origin_channel',
             'destination_channel','answered','duration','uniqueid')
    return {'rows':len(rows or []), 'well_formed':rows is not None,
            **{name:any(item[name] for item in details) for name in names}}


def cdr_runtime_status(modules, status):
    return {'custom_loaded':'cdr_custom.so' in modules, 'csv_loaded':'cdr_csv.so' in modules,
            'enabled':bool(re.search(r'(?im)^\s*Logging:\s*Enabled\s*$',status))}


def exercise_calls(container, prepared, report):
    from .asterisk_lab import cli, command
    checks = report['checks']
    report['calls'] = []
    report['call_protocol'] = {}
    report['cdr_checks'] = {}
    # O backend CDR custom abre o arquivo, mas requer o diretório pai existente.
    command(['docker','exec',container,'mkdir','-p','/var/log/asterisk/cdr-custom'])
    modules = cli(container, 'module show like cdr')
    status = cli(container, 'cdr show status')
    report['cdr_backend'] = cdr_runtime_status(modules,status)
    for tenant in TENANTS:
        for direction in DIRECTIONS:
            source, destination = ('1001','1002') if direction == 'forward' else ('1002','1001')
            suffix = ':'+tenant+':'+direction
            report['phase'] = 'call'+suffix
            for name in CHECKS:
                checks[name+suffix] = False
            with ExitStack() as resources, ThreadPoolExecutor(max_workers=1) as executor:
                caller = CallPeer('127.0.0.1',5061,prepared['ca'],tenant+'-'+source,
                                  prepared['credentials'][tenant+'-'+source])
                resources.callback(caller.close)
                callee = CallPeer('127.0.0.1',5061,prepared['ca'],tenant+'-'+destination,
                                  prepared['credentials'][tenant+'-'+destination])
                resources.callback(callee.close)
                report['call_protocol'][tenant+':'+direction] = {
                    'caller':caller.events, 'callee':callee.events}
                left, right = SrtpMedia(), SrtpMedia()
                resources.callback(left.close)
                resources.callback(right.close)
                checks['call_register'+suffix] = caller.register() == 200 and callee.register() == 200
                pending = executor.submit(callee.answer, right)
                try:
                    caller_dialog = caller.dial(destination, left)
                except Exception:
                    if pending.done():
                        pending.result()  # Preserve a causa da ponta chamada, não só timeout.
                    raise
                callee_dialog = pending.result(timeout=14)
                checks['call_established'+suffix] = True
                report['phase'] = 'media'+suffix
                media = exchange(left, right)
                report['calls'].append({'tenant':tenant, 'direction':direction,
                                        'media':media, 'profile':'AES_CM_128_HMAC_SHA1_80'})
                checks['srtp'+suffix] = media['authenticated'] and media['payloads_match']
                checks['tamper_rejected'+suffix] = media['tamper_rejected']
                checks['replay_rejected'+suffix] = media['replay_rejected']
                report['phase'] = 'hangup'+suffix
                pending = executor.submit(callee.await_hangup, callee_dialog)
                checks['hangup'+suffix] = caller.hangup(caller_dialog) == 200 and pending.result(timeout=12)
                caller.register(expires=0)
                callee.register(expires=0)
            deadline = time.monotonic()+8
            while time.monotonic() < deadline:
                active = cli(container, 'core show channels concise')
                cdr = command(['docker','exec',container,'cat','/var/log/asterisk/cdr-custom/Lab.csv'],check=False)
                checks['channels_cleared'+suffix] = not any(line.startswith('PJSIP/') for line in active.splitlines())
                checks['cdr'+suffix] = cdr.returncode == 0 and cdr_matches(cdr.stdout,tenant,source,destination)
                if checks['channels_cleared'+suffix] and checks['cdr'+suffix]:
                    break
                time.sleep(0.2)
            report['cdr_checks'][tenant+':'+direction] = {
                'readable':cdr.returncode == 0,
                **cdr_diagnostics(cdr.stdout,tenant,source,destination)}
            report['sip_call_tested'] = True
            report['rtp_tested'] = True
            report['srtp_tested'] = True
