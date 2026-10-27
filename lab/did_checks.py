"""Provas de DID com tronco TLS privado e observação de encaminhamento cruzado."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import re
import secrets
import threading
import time

from .call_checks import cdr_rows
from .did_evidence import prepare_cel, new_trace, evaluate_trace, evaluate_cdr, cel_backend_status
from .sip_calls import CallPeer, CallRejected, single
from .srtp_media import SrtpMedia, exchange

TRUNK = 't9-incoming'
CALLER = '199999'
DYNAMIC_DID = '5511900003333'
ORPHAN_DID = '5511900004444'
KNOWN = (('static-t1', '5511900001111', 't1'),
         ('static-t2', '5511900002222', 't2'),
         ('dynamic-t3', DYNAMIC_DID, 't3'))
REJECTED = (('unknown', '5511900009999'),
            ('deleted', DYNAMIC_DID), ('orphan', ORPHAN_DID))


def required_did_checks():
    checks = {'did_trunk_context', 'did_trunk_registered', 'did_contacts_cleared',
              'did_mapping_created', 'did_mapping_deleted', 'did_orphan_created','did_cel_backend'}
    checks.update(f'{name}:{case}' for case, _, _ in KNOWN for name in (
        'did_answered', 'did_srtp', 'did_hangup', 'did_cdr',
        'did_no_cross_ring', 'did_channels_cleared'))
    checks.update(f'{name}:{case}' for case, _ in REJECTED for name in (
        'did_rejected', 'did_no_cross_ring', 'did_channels_cleared', 'did_no_answered_cdr'))
    checks.update('did_cel:'+case for case in [item[0] for item in KNOWN+REJECTED])
    return checks


def prepare_dids(root, prepared, source_commit):
    """Adiciona só um endpoint autenticado; preserva os contextos exportados."""
    password = secrets.token_urlsafe(32)
    prepared['credentials'][TRUNK] = password
    target = prepared['conf']/'pjsip.conf'
    with target.open('a') as stream:
        stream.write(f'''
; Tronco descartável exclusivo do laboratório, com TLS e SRTP.
[{TRUNK}](endpoint-secure)
context=from-tdm-gateway
auth={TRUNK}
aors={TRUNK}
callerid=Private Lab <{CALLER}>

[{TRUNK}]
type=auth
auth_type=userpass
username={TRUNK}
password={password}

[{TRUNK}]
type=aor
max_contacts=1
remove_existing=yes
''')
    target.chmod(0o600)
    prepare_cel(prepared['conf'])


def did_cdr_fields(raw, previous_ids, tenant):
    rows = cdr_rows(raw)
    fresh = [row for row in rows or [] if row[8] not in previous_ids]
    coherent = len(fresh) == 1 and (
        fresh[0][0] == tenant and fresh[0][1] == CALLER and fresh[0][2] == '1001'
        and fresh[0][3] == tenant+'-internal'
        and re.fullmatch(r'PJSIP/'+TRUNK+r'-[0-9a-f]+',fresh[0][4]) is not None
        and re.fullmatch(r'PJSIP/'+re.escape(tenant)+r'-1001-[0-9a-f]+',fresh[0][5]) is not None
        and fresh[0][6] == 'ANSWERED' and fresh[0][7].isdigit() and int(fresh[0][7]) >= 1
        and re.fullmatch(r'[0-9]+\.[0-9]+',fresh[0][8]) is not None)
    return {'well_formed':rows is not None, 'one_new_record':len(fresh) == 1,
            'coherent_route':coherent}


def rejected_cdr_matches(raw, previous_ids):
    rows = cdr_rows(raw)
    fresh = [row for row in rows or [] if row[8] not in previous_ids]
    return rows is not None and bool(fresh) and all(
        not row[0] and row[1] == CALLER and row[2] == 'did-desconhecido'
        and row[3] == 'from-tdm-gateway'
        and re.fullmatch(r'PJSIP/'+TRUNK+r'-[0-9a-f]+',row[4]) is not None
        and not row[5] and row[6] in ('FAILED','NO ANSWER','BUSY','CONGESTION')
        and row[7] == '0' and re.fullmatch(r'[0-9]+\.[0-9]+',row[8]) is not None
        for row in fresh)


def observe_peer(peer, stop, ready):
    """Falhas de leitura invalidam o aceite; INVITEs inesperados recebem 486."""
    result = {'healthy':True, 'invites':0}
    ready.set()
    try:
        while not stop.is_set():
            try:
                start, headers, _ = peer.next_message(time.monotonic()+0.2)
            except TimeoutError:
                continue
            if start.startswith('INVITE '):
                result['invites'] += 1
                local = single(headers, 'to')+';tag='+secrets.token_hex(8)
                peer.send_response(headers,486,local=local)
            elif not start.startswith('ACK '):
                result['healthy'] = False
    except (OSError, ValueError, ConnectionError):
        result['healthy'] = False
    return result


def exercise_dids(container, prepared, report):
    from .asterisk_lab import cli, command
    checks = report['checks']
    checks.update({name:False for name in required_did_checks()})
    report['did_results'] = []
    report['did_protocol'] = {}
    report['did_cel_results'] = {}
    modules = cli(container,'module show like cel_custom')
    status = cli(container,'cel show status')
    report['did_cel_backend'] = cel_backend_status(modules,status)
    checks['did_cel_backend'] = all(report['did_cel_backend'].values())

    def cel_snapshot():
        result = command(['docker','exec',container,'head','-c','1048577',
                          '/var/log/asterisk/cel-custom/Lab.csv'])
        if len(result.stdout)>1024*1024:
            raise ValueError('rastro CEL excessivo')
        return result.stdout

    def cdr_snapshot():
        result = command(['docker','exec',container,'cat','/var/log/asterisk/cdr-custom/Lab.csv'])
        if cdr_rows(result.stdout) is None:
            raise ValueError('CDR do laboratório inválido')
        return result.stdout

    def db_value(family, key):
        value = cli(container, f'database get {family} {key}').strip()
        return value[7:] if value.startswith('Value: ') else None

    cli(container, f'database put tenant-did {DYNAMIC_DID} t3')
    cli(container, f'database put vip-t3 {CALLER} 1001')
    checks['did_mapping_created'] = (db_value('tenant-did',DYNAMIC_DID) == 't3'
                                     and db_value('vip-t3',CALLER) == '1001')
    cli(container, f'database put tenant-did {ORPHAN_DID} t99')
    checks['did_orphan_created'] = db_value('tenant-did',ORPHAN_DID) == 't99'
    endpoint = cli(container, 'pjsip show endpoint '+TRUNK)
    checks['did_trunk_context'] = re.search(
        r'(?im)^\s*context\s*:\s*from-tdm-gateway\s*$',endpoint) is not None

    with ExitStack() as resources:
        caller = CallPeer('127.0.0.1',5061,prepared['ca'],TRUNK,prepared['credentials'][TRUNK])
        resources.callback(caller.close)
        receivers = {}
        registered = caller.register() == 200
        for tenant in ('t1','t2','t3'):
            name = tenant+'-1001'
            peer = CallPeer('127.0.0.1',5061,prepared['ca'],name,prepared['credentials'][name])
            resources.callback(peer.close)
            receivers[tenant] = peer
            registered = peer.register() == 200 and registered
        checks['did_trunk_registered'] = registered
        scenarios = [(case,number,tenant) for case,number,tenant in KNOWN]
        scenarios += [(case,number,None) for case,number in REJECTED]
        for case, number, tenant in scenarios:
            report['phase'] = 'did:'+case
            if case == 'deleted':
                cli(container, f'database del tenant-did {DYNAMIC_DID}')
                checks['did_mapping_deleted'] = db_value('tenant-did',DYNAMIC_DID) is None
            previous_ids = {row[8] for row in cdr_rows(cdr_snapshot())}
            previous_trace = cel_snapshot()
            stop = threading.Event()
            with ThreadPoolExecutor(max_workers=4) as executor, ExitStack() as media_resources:
                observers = []
                try:
                    for other, peer in receivers.items():
                        if other == tenant:
                            continue
                        ready = threading.Event()
                        future = executor.submit(observe_peer,peer,stop,ready)
                        observers.append(future)
                        if not ready.wait(2):
                            raise TimeoutError('observador de DID indisponível')
                    left = SrtpMedia()
                    media_resources.callback(left.close)
                    report['did_protocol'][case] = caller.events = []
                    if tenant:
                        right = SrtpMedia()
                        media_resources.callback(right.close)
                        callee = receivers[tenant]
                        pending = executor.submit(callee.answer,right)
                        dialog = caller.dial(number,left)
                        remote = pending.result(timeout=14)
                        checks['did_answered:'+case] = True
                        media = exchange(left,right)
                        checks['did_srtp:'+case] = media['authenticated'] and media['payloads_match']
                        pending = executor.submit(callee.await_hangup,remote)
                        checks['did_hangup:'+case] = caller.hangup(dialog) == 200 and pending.result(timeout=12)
                    else:
                        try:
                            dialog = caller.dial(number,left)
                        except CallRejected as rejected:
                            checks['did_rejected:'+case] = rejected.code == 403
                        else:
                            # Uma aceitação indevida precisa ser encerrada, nunca contada como rejeição.
                            caller.hangup(dialog)
                    # Mantém os observadores ativos também durante a escrita do CDR.
                    deadline = time.monotonic()+8
                    while time.monotonic() < deadline:
                        active = cli(container,'core show channels concise')
                        checks['did_channels_cleared:'+case] = not any(
                            line.startswith('PJSIP/') for line in active.splitlines())
                        raw = cdr_snapshot()
                        if tenant:
                            checks['did_cdr:'+case] = all(did_cdr_fields(raw,previous_ids,tenant).values())
                            recorded = checks['did_cdr:'+case]
                        else:
                            checks['did_no_answered_cdr:'+case] = rejected_cdr_matches(raw,previous_ids)
                            recorded = checks['did_no_answered_cdr:'+case]
                        trace = evaluate_trace(new_trace(previous_trace,cel_snapshot()),tenant)
                        correlated_cdr = evaluate_cdr(raw,trace,tenant)
                        trace_fields = ('well_formed','correlated','complete','isolated')
                        trace_fields += ('routed',) if tenant else ('never_answered','no_delivery','no_side_effects','cause_21')
                        entry_did = trace.get('_original_did')==number
                        checks['did_cel:'+case] = (entry_did and all(trace.get(key) is True for key in trace_fields)
                                                    and all(correlated_cdr.values()))
                        report['did_cel_results'][case] = {
                            'entry_did':entry_did,
                            'trace':{key:value for key,value in trace.items() if type(value) is bool},
                            'cdr':correlated_cdr}
                        if checks['did_channels_cleared:'+case] and recorded and checks['did_cel:'+case]:
                            break
                        time.sleep(0.2)
                    time.sleep(0.25)
                finally:
                    stop.set()
                    observations = [future.result(timeout=2) for future in observers]
                    checks['did_no_cross_ring:'+case] = (len(observations) == (2 if tenant else 3)
                        and all(item['healthy'] is True and item['invites'] == 0 for item in observations))
                    report['did_results'].append({'case':case,'expected_tenant':tenant,
                        'observers':observations})
        unregistered = caller.register(expires=0) == 200
        for peer in receivers.values():
            unregistered = peer.register(expires=0) == 200 and unregistered
        contacts = cli(container,'pjsip show contacts')
        checks['did_contacts_cleared'] = unregistered and not any(
            name+'/' in contacts for name in (TRUNK,'t1-1001','t2-1001','t3-1001'))
    report['live_did_routing_tested'] = all(checks[name] is True for name in required_did_checks())
