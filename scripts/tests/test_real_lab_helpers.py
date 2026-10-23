"""Contratos do laboratório: framing real e segredos fora do checkout."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def test_tcp_framing_retains_next_response_and_waits_for_body():
    from lab.sip_tls import pop_message
    first = b'SIP/2.0 200 OK\r\nContent-Length: 3\r\n\r\nabc'
    second = b'SIP/2.0 401 Unauthorized\r\nContent-Length: 0\r\n\r\n'
    assert pop_message(first[:-1]) == (None, first[:-1])
    message, rest = pop_message(first + second)
    assert message == first
    assert rest == second


def test_sip_framing_rejects_invalid_and_oversized_lengths():
    from lab.sip_tls import pop_message
    for length in ('-1', 'abc', '99999999'):
        with pytest.raises(ValueError):
            pop_message(f'SIP/2.0 200 OK\r\nContent-Length: {length}\r\n\r\n'.encode())
    with pytest.raises(ValueError):
        pop_message(b'x' * 65537)
    with pytest.raises(ValueError):
        pop_message(b'SIP/2.0 200 OK\r\nContent-Length: 0\r\nContent-Length: 1\r\n\r\nx')


def test_digest_matches_rfc2617_known_vector():
    from lab.sip_tls import digest_authorization
    # Vetor RFC 2617, calculado independentemente do gerador SIP.
    value = digest_authorization(
        'Digest realm="testrealm@host.com", qop="auth,auth-int", '
        'nonce="dcd98b7102dd2f0e8b11d0f600bfb0c093", opaque="5ccc069c403ebaf9f0171e9517f40e41"',
        username='Mufasa', password='Circle Of Life', method='GET',
        uri='/dir/index.html', cnonce='0a4f113b',
    )
    assert 'response="6629fae49393a05397450978507c4ef1"' in value
    assert 'qop=auth' in value
    assert 'nc=00000001' in value
    assert 'opaque="5ccc069c403ebaf9f0171e9517f40e41"' in value


def test_digest_rejects_unsupported_algorithm_and_qop():
    from lab.sip_tls import digest_authorization
    for challenge in ('Basic realm="a"', 'Digest realm="a",nonce="b",algorithm=SHA-999',
                      'Digest realm="a",nonce="b",qop="auth-int"', 'Digest realm="a"'):
        with pytest.raises(ValueError):
            digest_authorization(challenge, username='u', password='p', method='REGISTER', uri='sip:localhost')


def test_private_lab_copy_rotates_secrets_and_preserves_source(tmp_path):
    from lab.asterisk_lab import prepare
    before = (ROOT / 'asterisk/pjsip.conf').read_bytes()
    prepared = prepare(ROOT, tmp_path / 'private')
    assert (ROOT / 'asterisk/pjsip.conf').read_bytes() == before
    conf = (tmp_path / 'private/asterisk/pjsip.conf').read_text()
    assert 'troque_esta_senha' not in conf
    assert 'bind=0.0.0.0' not in conf
    assert len(prepared['credentials']['t1-1001']) >= 24
    assert len(set(prepared['credentials'].values())) == len(prepared['credentials'])
    assert (tmp_path / 'private').stat().st_mode & 0o077 == 0
    assert (tmp_path / 'private/asterisk/pjsip.conf').stat().st_mode & 0o077 == 0
    assert (tmp_path / 'private/asterisk/pjsip_tenants/t3.conf').exists()


def test_sip_client_rejects_non_loopback_target_before_connecting(tmp_path):
    from lab.sip_tls import SipTLS
    with pytest.raises(ValueError):
        SipTLS('example.com', 5061, tmp_path/'ca.crt', 'user', 'secret')


def test_summary_requires_every_named_check_and_never_approves_empty_results():
    from lab.asterisk_lab import summarize
    checks = {'real_runtime': True, 'tls_transport': True, 'wss_transport': True,
              'container_removed': True, 'checkout_clean': True,
              'runtime_mounts': True, 'source_label': True}
    for tid in ('t1', 't2', 't3'):
        for name in ('context', 'register', 'contact', 'unregister', 'wrong_password'):
            checks[name+':'+tid] = True
    assert summarize(checks) == {'passed': 22, 'total': 22, 'success': True}
    assert summarize({})['success'] is False
    assert summarize({**checks, 'register:t2': False})['success'] is False
    assert summarize({k:v for k,v in checks.items() if k != 'contact:t3'})['success'] is False
    assert summarize({**checks, 'unregister:t1': 1})['success'] is False


def test_startup_diagnostics_never_copy_raw_lines_or_credentials():
    from lab.asterisk_lab import diagnose
    import json
    raw = ("Unable to open Asterisk database '/private/SECRET_PRIVATE': unable to open database file\n"
           "Inheritance requested, but category 'endpoint-base!' does not exist\n"
           "Unable to open pid file '/run/SECRET_PRIVATE': Permission denied\n"
           'Authorization: Digest response="SECRET_PRIVATE"\n')
    result = diagnose(raw)
    assert result['missing_template'] is True
    assert result['permission_denied'] is True
    assert result['database_unavailable'] is True
    assert 'SECRET_PRIVATE' not in json.dumps(result)
    assert all(type(value) is bool for value in result.values())


def test_unsolicited_mwi_is_acknowledged_without_accepting_wrong_transaction():
    import socket
    import threading
    from lab.sip_tls import SipTLS, parse_message
    client, server = socket.socketpair()
    client.settimeout(2)
    server.settimeout(2)
    peer = SipTLS.__new__(SipTLS)
    peer.connection = client
    peer.username, peer.port = 't1-1001', 55000
    peer.call_id, peer.tag, peer.cseq, peer.buffer = 'register@localhost', 'client', 0, b''
    observed = []

    def serve():
        try:
            request = server.recv(8192)
            _, headers, _ = parse_message(request)
            notify = (b'NOTIFY sip:t1-1001@localhost SIP/2.0\r\n'
                      b'Via: SIP/2.0/TLS localhost;branch=z9hG4bKmwi\r\n'
                      b'From: <sip:asterisk@localhost>;tag=server\r\n'
                      b'To: <sip:t1-1001@localhost>;tag=client\r\n'
                      b'Call-ID: mwi@localhost\r\nCSeq: 1 NOTIFY\r\n'
                      b'Content-Length: 0\r\n\r\n')
            response = (f'SIP/2.0 200 OK\r\nCall-ID: {headers["call-id"][0]}\r\n'
                        f'CSeq: {headers["cseq"][0]}\r\nContent-Length: 0\r\n\r\n').encode()
            server.sendall(notify + response)
            acknowledgement = server.recv(8192)
            if acknowledgement:
                observed.append(parse_message(acknowledgement))
        finally:
            server.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        code, _ = peer.request('REGISTER', 'sip:localhost')
        assert code == 200
        thread.join(3)
        assert not thread.is_alive()
        assert observed[0][0] == 'SIP/2.0 200 OK'
        assert observed[0][1]['call-id'] == ['mwi@localhost']
        assert observed[0][1]['cseq'] == ['1 NOTIFY']
    finally:
        client.close()


def test_response_for_another_transaction_still_fails_closed():
    import socket
    import threading
    from lab.sip_tls import SipTLS
    client, server = socket.socketpair()
    client.settimeout(2)
    server.settimeout(2)
    peer = SipTLS.__new__(SipTLS)
    peer.connection = client
    peer.username, peer.port = 't1-1001', 55000
    peer.call_id, peer.tag, peer.cseq, peer.buffer = 'register@localhost', 'client', 0, b''

    def serve():
        try:
            server.recv(8192)
            server.sendall(b'SIP/2.0 200 OK\r\nCall-ID: wrong@localhost\r\n'
                           b'CSeq: 1 REGISTER\r\nContent-Length: 0\r\n\r\n')
        finally:
            server.close()
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        with pytest.raises(ValueError, match='outra transação'):
            peer.request('REGISTER', 'sip:localhost')
    finally:
        client.close()
        thread.join(3)
