"""Contratos de diálogo exercitados com sockets reais e mensagens SIP completas."""
from pathlib import Path
import socket
import sys
import threading

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lab.sip_tls import parse_message, pop_message


READ_BUFFERS = {}


def read_message(connection):
    data = READ_BUFFERS.pop(connection, b'')
    while True:
        message, rest = pop_message(data)
        if message is not None:
            READ_BUFFERS[connection] = rest
            return parse_message(message)
        chunk = connection.recv(8192)
        if not chunk:
            raise ConnectionError('test SIP server EOF')
        data += chunk


def response(headers, code, extra='', body=b''):
    lines = [f'SIP/2.0 {code} Lab', *['Via: '+v for v in headers['via']],
             'From: '+headers['from'][0], 'To: '+headers['to'][0]+('' if ';tag=' in headers['to'][0] else ';tag=asterisk'),
             'Call-ID: '+headers['call-id'][0], 'CSeq: '+headers['cseq'][0]]
    if extra:
        lines += extra.split('\r\n')
    return ('\r\n'.join(lines)+f'\r\nContent-Length: {len(body)}\r\n\r\n').encode()+body


def peer_on(connection):
    from lab.sip_calls import CallPeer
    peer = CallPeer.__new__(CallPeer)
    peer.connection = connection
    peer.username, peer.password, peer.port, peer.target_port = 't1-1001', 'PRIVATE', 55000, 5061
    peer.call_id, peer.tag, peer.cseq, peer.buffer = 'old@localhost', 'old', 0, b''
    peer.events = []
    return peer


def test_call_authenticates_acknowledges_and_hangs_up_correlated_dialogue():
    from lab.srtp_media import SrtpMedia
    client, server = socket.socketpair()
    client.settimeout(2)
    server.settimeout(2)
    peer, media, remote_media = peer_on(client), SrtpMedia(), SrtpMedia()
    observed, failures = [], []

    def serve():
        try:
            _, initial, _ = read_message(server)
            server.sendall(response(initial, 401, 'WWW-Authenticate: Digest realm="asterisk", nonce="test", algorithm=MD5, qop="auth"'))
            start, ack, _ = read_message(server)
            observed.append(start.startswith('ACK ') and ack['cseq'] == ['1 ACK'])
            _, invite, body = read_message(server)
            observed.append(invite['authorization'][0].startswith('Digest username="t1-1001"'))
            observed.append(b'RTP/SAVP' in body)
            server.sendall(response(invite, 200, 'Contact: <sip:127.0.0.1:5061;transport=TLS>\r\nContent-Type: application/sdp', remote_media.offer()))
            start, ack, _ = read_message(server)
            observed.append(start.startswith('ACK ') and ack['cseq'] == ['2 ACK'])
            start, bye, _ = read_message(server)
            observed.append(start.startswith('BYE ') and bye['cseq'] == ['3 BYE'])
            observed.append(bye['to'][0].endswith(';tag=asterisk'))
            server.sendall(response(bye, 200))
        except BaseException as exc:
            failures.append(exc)
        finally:
            server.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        dialog = peer.dial('1002', media)
        assert peer.hangup(dialog) == 200
        thread.join(3)
        assert not thread.is_alive()
        assert not failures
        assert observed == [True] * 6
        assert media.address == ('127.0.0.1', remote_media.port)
        assert peer.events == ['invite_sent', 'response:401', 'authenticated_invite_sent',
                               'response:200', 'ack_sent', 'bye_sent', 'response:200']
    finally:
        peer.close()
        media.close()
        remote_media.close()


def test_other_transaction_final_response_cannot_establish_call():
    from lab.srtp_media import SrtpMedia
    client, server = socket.socketpair()
    peer, media = peer_on(client), SrtpMedia()

    def serve():
        try:
            _, headers, _ = read_message(server)
            headers['call-id'] = ['unrelated@localhost']
            server.sendall(response(headers, 200))
        finally:
            server.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        with pytest.raises(ValueError, match='transação'):
            peer.dial('1002', media)
    finally:
        peer.close()
        media.close()
        thread.join(3)


def test_incoming_bye_with_wrong_dialogue_is_rejected():
    from lab.sip_calls import Dialog
    client, server = socket.socketpair()
    peer = peer_on(client)
    dialog = Dialog('expected', '<sip:t1-1001@localhost>;tag=local',
                    '<sip:pbx@localhost>;tag=remote', 'sip:pbx@127.0.0.1:5061', 1)
    server.sendall(b'BYE sip:t1-1001@localhost SIP/2.0\r\nVia: SIP/2.0/TLS localhost;branch=z9hG4bKx\r\n'
                   b'From: <sip:pbx@localhost>;tag=remote\r\nTo: <sip:t1-1001@localhost>;tag=local\r\n'
                   b'Call-ID: other\r\nCSeq: 2 BYE\r\nContent-Length: 0\r\n\r\n')
    try:
        with pytest.raises(ValueError, match='diálogo'):
            peer.await_hangup(dialog)
    finally:
        client.close()
        server.close()


@pytest.mark.parametrize('uri', [
    'sip:asterisk@127.0.0.1:5061;transport=TLS',
    'sip:127.0.0.1:5061;transport=TLS',
    'sip:127.0.0.1:5061;transport=tls',
])
def test_contact_transport_is_case_insensitive_for_asterisk_wire_format(uri):
    from lab.sip_calls import contact_uri
    assert contact_uri({'contact':['<'+uri+'>']}) == uri


@pytest.mark.parametrize('uri', ['sip:asterisk@127.0.0.1:0', 'sip:asterisk@127.0.0.1:65536',
                                'sip:asterisk@192.0.2.1:5061;transport=tls',
                                'sip:127.0.0.1.example.invalid:5061;transport=tls'])
def test_contact_rejects_external_host_and_invalid_port(uri):
    from lab.sip_calls import contact_uri
    with pytest.raises(ValueError):
        contact_uri({'contact':['<'+uri+'>']})

def test_dtmf_hangup_accepts_correlated_remote_bye_without_wrong_transaction():
    from lab.sip_calls import Dialog
    client, server = socket.socketpair()
    client.settimeout(2)
    server.settimeout(2)
    peer = peer_on(client)
    dialog = Dialog('dtmf-test@localhost',
                    '<sip:t1-1001@localhost>;tag=local',
                    '<sip:asterisk@localhost>;tag=remote',
                    'sip:asterisk@127.0.0.1:5061;transport=tls', 2)
    seen = []
    errors = []

    def serve():
        try:
            start, headers, _ = read_message(server)
            assert start.startswith('BYE ')
            assert headers['call-id'] == [dialog.call_id]
            wire = ('BYE sip:t1-1001@localhost SIP/2.0\r\n'
                    'Via: SIP/2.0/TLS localhost;branch=z9hG4bKtest\r\n'
                    'From: '+dialog.remote+'\r\nTo: '+dialog.local+'\r\n'
                    'Call-ID: '+dialog.call_id+'\r\nCSeq: 77 BYE\r\n'
                    'Content-Length: 0\r\n\r\n')
            server.sendall(wire.encode('ascii'))
            start, response_headers, _ = read_message(server)
            seen.append(start.startswith('SIP/2.0 200 '))
            seen.append(response_headers['call-id'] == [dialog.call_id])
            # A resposta ao BYE iniciado pelo cliente ainda precisa ser consumida.
            server.sendall(response(headers, 200))
        except BaseException as exc:
            errors.append(type(exc).__name__)
        finally:
            server.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        assert peer.hangup_or_accept_remote_bye(dialog) == 200
        thread.join(3)
        assert seen == [True, True]
        assert not errors
        assert 'remote_bye_acknowledged' in peer.events
    finally:
        peer.close()
        thread.join(3)


def test_dtmf_hangup_rejects_remote_bye_from_other_dialogue():
    from lab.sip_calls import Dialog
    client, server = socket.socketpair()
    client.settimeout(2)
    server.settimeout(2)
    peer = peer_on(client)
    dialog = Dialog('expected@localhost',
                    '<sip:t1-1001@localhost>;tag=local',
                    '<sip:asterisk@localhost>;tag=remote',
                    'sip:asterisk@127.0.0.1:5061;transport=tls', 2)

    def serve():
        try:
            read_message(server)
            server.sendall((
                'BYE sip:t1-1001@localhost SIP/2.0\r\n'
                'Via: SIP/2.0/TLS localhost;branch=z9hG4bKtest\r\n'
                'From: '+dialog.remote+'\r\nTo: '+dialog.local+'\r\n'
                'Call-ID: unrelated@localhost\r\nCSeq: 77 BYE\r\n'
                'Content-Length: 0\r\n\r\n').encode('ascii'))
        finally:
            server.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        with pytest.raises(ValueError, match='diálogo'):
            peer.hangup_or_accept_remote_bye(dialog)
        assert 'remote_bye_acknowledged' not in peer.events
    finally:
        peer.close()
        thread.join(3)
