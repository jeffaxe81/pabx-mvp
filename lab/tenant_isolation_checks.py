"""Tentativas SIP reais entre tenants no Asterisk descartável.

Este laboratório comprova somente negativa de discagem de endpoint externo
à empresa do chamador; não substitui isolamento de API, fila, voicemail,
DID, volume de gravações ou autorização operacional.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import re
import threading
import time

from .call_checks import cdr_rows
from .did_checks import observe_peer
from .sip_calls import CallPeer, CallRejected
from .srtp_media import SrtpMedia

CROSS_CASES = (
    ('t1-to-t2', 't1-1001', 't2-1001'),
    ('t2-to-t1', 't2-1001', 't1-1001'),
    ('t3-to-t2', 't3-1001', 't2-1001'),
)
CHECK_NAMES = ('registered', 'sip_rejected', 'no_cross_ring',
               'channels_cleared', 'cdr_no_delivery')


def required_isolation_checks():
    return {name + ':' + case for case, _, _ in CROSS_CASES
            for name in CHECK_NAMES}


def rejected_cdr_is_isolated(raw, previous_ids, caller, target):
    """Correlaciona registro novo de rejeição, sem áudio ou canal B."""
    rows = cdr_rows(raw)
    if rows is None or not isinstance(previous_ids, set):
        return False
    fresh = [row for row in rows if row[8] not in previous_ids]
    tenant, number = caller.split('-', 1)
    return bool(fresh) and all(
        row[1] == number
        and row[2] == target
        and row[3] == tenant + '-internal'
        and re.fullmatch(r'PJSIP/' + re.escape(caller) + r'-[0-9a-f]+', row[4]) is not None
        and row[5] == ''
        and row[6] != 'ANSWERED'
        and row[7] == '0'
        and re.fullmatch(r'[0-9]+\.[0-9]+', row[8]) is not None
        for row in fresh
    )


def exercise_isolation(container, prepared, report):
    """Executa negativos com observador autenticado no ramal estrangeiro."""
    from .asterisk_lab import cli, command

    checks = report['checks']
    checks.update({key: False for key in required_isolation_checks()})
    report['sip_isolation_cases'] = {}
    report['live_sip_extension_isolation_tested'] = False

    def snapshot():
        answer = command(['docker', 'exec', container, 'cat',
                          '/var/log/asterisk/cdr-custom/Lab.csv'], check=False)
        if answer.returncode or cdr_rows(answer.stdout) is None:
            raise ValueError('CDR do isolamento ausente ou inválido')
        return answer.stdout

    for case, source, destination in CROSS_CASES:
        report['phase'] = 'sip-isolation:' + case
        prior = {row[8] for row in cdr_rows(snapshot())}
        stop, ready = threading.Event(), threading.Event()

        with ExitStack() as resources, ThreadPoolExecutor(max_workers=1) as executor:
            caller = CallPeer('127.0.0.1', 5061, prepared['ca'],
                              source, prepared['credentials'][source])
            resources.callback(caller.close)
            foreign = CallPeer('127.0.0.1', 5061, prepared['ca'],
                               destination, prepared['credentials'][destination])
            resources.callback(foreign.close)
            checks['registered:' + case] = (
                caller.register() == 200 and foreign.register() == 200
            )
            if not checks['registered:' + case]:
                raise ValueError('registro SIP negativo não confirmado')
            future = executor.submit(observe_peer, foreign, stop, ready)
            try:
                if not ready.wait(2):
                    raise TimeoutError('observador SIP não iniciou')
                media = SrtpMedia()
                resources.callback(media.close)
                code = None
                try:
                    dialog = caller.dial(destination, media)
                except CallRejected as rejected:
                    code = rejected.code
                else:
                    # A resposta 2xx é violação de isolamento; encerra diálogo.
                    caller.hangup(dialog)
                checks['sip_rejected:' + case] = code in (404, 484)
                # Janela de observação inclui SIP assíncrono após a negativa.
                time.sleep(0.5)
            finally:
                stop.set()
                observation = future.result(timeout=5)
            checks['no_cross_ring:' + case] = (
                observation == {'healthy': True, 'invites': 0}
            )
            caller.register(expires=0)
            foreign.register(expires=0)

        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            channels = cli(container, 'core show channels concise')
            clean = not any(row.startswith('PJSIP/') for row in channels.splitlines())
            cdr = rejected_cdr_is_isolated(snapshot(), prior, source, destination)
            checks['channels_cleared:' + case] = clean
            checks['cdr_no_delivery:' + case] = cdr
            if clean and cdr:
                break
            time.sleep(0.2)
        report['sip_isolation_cases'][case] = {
            'rejected': checks['sip_rejected:' + case],
            'no_cross_ring': checks['no_cross_ring:' + case],
            'cdr_no_delivery': checks['cdr_no_delivery:' + case],
        }
    report['live_sip_extension_isolation_tested'] = all(
        checks[name] is True for name in required_isolation_checks()
    )
