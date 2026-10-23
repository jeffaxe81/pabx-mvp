"""Aceites de DID não podem reutilizar CDR nem ocultar falhas de observação."""
import json
from pathlib import Path
import socket
import sys
import threading

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

ROW = '"t2","199999","1001","t2-internal","PJSIP/t9-incoming-00000001","PJSIP/t2-1001-00000002","ANSWERED","2","123.45"\n'


def test_did_cdr_requires_new_id_correct_company_and_both_channels():
    from lab.did_checks import did_cdr_fields
    assert all(did_cdr_fields(ROW, set(), 't2').values())
    assert not all(did_cdr_fields(ROW, {'123.45'}, 't2').values())
    for before, after in [('"t2",', '"t1",'), ('t2-internal', 't1-internal'),
                          ('PJSIP/t2-1001-', 'PJSIP/t1-1001-'),
                          ('PJSIP/t9-incoming-', 'PJSIP/t1-1001-'),
                          ('ANSWERED', 'NO ANSWER'), ('"2","123.45"', '"0","123.45"')]:
        assert not all(did_cdr_fields(ROW.replace(before, after), set(), 't2').values())
    assert not all(did_cdr_fields(ROW.replace('"t2",','"t1",') +
                                  ROW.replace('t2-internal','t1-internal'), set(), 't2').values())
    for raw in ('', 'garbage', ROW+'"unterminated', ROW.replace(',"123.45"','')):
        assert not all(did_cdr_fields(raw, set(), 't2').values())


def test_did_diagnostics_do_not_copy_private_fields():
    from lab.did_checks import did_cdr_fields
    result = did_cdr_fields(ROW.replace('199999', 'PRIVATE_NUMBER'), set(), 't2')
    assert not all(result.values())
    assert 'PRIVATE_NUMBER' not in json.dumps(result)
    assert all(type(value) is bool for value in result.values())


def test_did_summary_requires_every_case_and_strict_booleans():
    from lab.asterisk_lab import summarize
    from lab.call_checks import required_call_checks
    from lab.did_checks import required_did_checks
    baseline = {'real_runtime', 'tls_transport', 'wss_transport', 'container_removed',
                'checkout_clean', 'runtime_mounts', 'source_label'}
    baseline.update(name+':'+tid for tid in ('t1','t2','t3')
                    for name in ('context','register','contact','unregister','wrong_password'))
    complete = {name: True for name in baseline | required_call_checks() | required_did_checks()}
    assert summarize(complete, calls=True, dids=True)['success'] is True
    for key in ('did_rejected:unknown', 'did_rejected:deleted', 'did_rejected:orphan',
                'did_cdr:dynamic-t3', 'did_no_cross_ring:static-t2'):
        assert key in complete
        assert summarize({k:v for k,v in complete.items() if k != key}, calls=True, dids=True)['success'] is False
        assert summarize({**complete, key: 1}, calls=True, dids=True)['success'] is False
    assert summarize(complete, calls=True)['success'] is False


def test_did_mode_requires_calls_before_reading_checkout(tmp_path):
    from lab.asterisk_lab import main
    with pytest.raises(SystemExit) as error:
        main(['--dids', '--report', str(tmp_path/'report.json')])
    assert error.value.code == 2


def test_did_mode_is_forwarded_to_runner_and_report_is_preserved(tmp_path,monkeypatch):
    from lab import asterisk_lab
    def run(root,report,*,calls=False,webrtc=False,dids=False):
        report.update(did_mode_tested=calls and dids,success=calls and dids)
        return calls and dids
    monkeypatch.setattr(asterisk_lab,'run',run)
    output = tmp_path/'report.json'
    assert asterisk_lab.main(['--calls','--dids','--report',str(output)]) == 0
    assert json.loads(output.read_text()) == {'did_mode_tested':True,'success':True}


def test_did_preparation_only_adds_private_loopback_authenticated_trunk(tmp_path):
    from lab.asterisk_lab import prepare
    from lab.call_checks import prepare_calls
    from lab.did_checks import prepare_dids
    original = (ROOT/'asterisk/pjsip.conf').read_bytes()
    prepared = prepare(ROOT, tmp_path/'private')
    prepare_calls(ROOT, prepared, 'HEAD')
    before = (prepared['conf']/'pjsip.conf').read_text()
    prepare_dids(ROOT, prepared, 'HEAD')
    content = (prepared['conf']/'pjsip.conf').read_text()
    assert content.startswith(before)
    assert '[t9-incoming](endpoint-secure)' in content
    assert 'context=from-tdm-gateway' in content[len(before):]
    assert 'identify_by=ip' not in content[len(before):]
    assert 'auth=t9-incoming' in content[len(before):]
    assert prepared['credentials']['t9-incoming'] in content
    assert len(prepared['credentials']['t9-incoming']) >= 32
    assert (prepared['conf']/'pjsip.conf').stat().st_mode & 0o077 == 0
    assert (ROOT/'asterisk/pjsip.conf').read_bytes() == original


def observed_peer(connection):
    from lab.sip_calls import CallPeer
    peer = CallPeer.__new__(CallPeer)
    peer.connection, peer.buffer, peer.events = connection, b'', []
    peer.username, peer.port = 't1-1001', 55000
    return peer


def test_observer_detects_foreign_ring_and_acknowledges_instead_of_waiting():
    from lab.did_checks import observe_peer
    client, server = socket.socketpair()
    stop, ready = threading.Event(), threading.Event()
    results = []
    thread = threading.Thread(target=lambda:results.append(observe_peer(observed_peer(client), stop, ready)))
    thread.start()
    try:
        assert ready.wait(1)
        server.sendall(b'INVITE sip:t1-1001@localhost SIP/2.0\r\n'
                      b'Via: SIP/2.0/TLS 127.0.0.1;branch=z9hG4bKtest\r\n'
                      b'From: <sip:private@localhost>;tag=foreign\r\n'
                      b'To: <sip:t1-1001@localhost>\r\n'
                      b'Call-ID: private@localhost\r\nCSeq: 1 INVITE\r\n'
                      b'Content-Length: 0\r\n\r\n')
        server.settimeout(2)
        assert server.recv(8192).startswith(b'SIP/2.0 486 ')
        stop.set()
        thread.join(2)
        assert not thread.is_alive()
        assert results == [{'healthy':True, 'invites':1}]
    finally:
        stop.set()
        thread.join(2)
        client.close()
        server.close()


def test_observer_eof_cannot_be_reported_as_no_foreign_ring():
    from lab.did_checks import observe_peer
    client, server = socket.socketpair()
    server.close()
    try:
        assert observe_peer(observed_peer(client), threading.Event(), threading.Event()) == {
            'healthy':False, 'invites':0}
    finally:
        client.close()


def test_healthy_observer_can_stop_without_receiving_a_call():
    from lab.did_checks import observe_peer
    client,server = socket.socketpair()
    stop,ready = threading.Event(),threading.Event()
    result = []
    thread = threading.Thread(target=lambda:result.append(observe_peer(observed_peer(client),stop,ready)))
    thread.start()
    try:
        assert ready.wait(1)
        stop.set()
        thread.join(1)
        assert not thread.is_alive()
        assert result == [{'healthy':True,'invites':0}]
    finally:
        stop.set()
        thread.join(1)
        client.close()
        server.close()
