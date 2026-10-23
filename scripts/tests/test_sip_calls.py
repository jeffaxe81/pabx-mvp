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
            server.sendall(response(invite, 200, 'Contact: <sip:asterisk@127.0.0.1:5061;transport=tls>\r\nContent-Type: application/sdp', remote_media.offer()))
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
