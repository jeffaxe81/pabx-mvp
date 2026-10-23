"""DIDs E.164 e rejeições são exercitados com framing SIP real em sockets."""
import socket
import threading

import pytest

from test_sip_calls import peer_on, read_message, response


@pytest.mark.parametrize('number', ['5511900001111', '123456789012345'])
def test_did_rejection_exposes_correlated_status_and_sends_final_ack(number):
    from lab.sip_calls import CallRejected
    from lab.srtp_media import SrtpMedia
    client, server = socket.socketpair()
    client.settimeout(2)
    server.settimeout(2)
    peer, media = peer_on(client), SrtpMedia()
    observed, errors = [], []

    def serve():
        try:
            start, initial, _ = read_message(server)
            observed.append(start == f'INVITE sip:{number}@127.0.0.1:5061;transport=tls SIP/2.0')
            server.sendall(response(initial,401,'WWW-Authenticate: Digest realm="asterisk", nonce="private", qop="auth"'))
            observed.append(read_message(server)[0].startswith('ACK '))
            _, authenticated, _ = read_message(server)
            server.sendall(response(authenticated,403))
            start, ack, _ = read_message(server)
            observed.append(start.startswith('ACK ') and ack['cseq'] == ['2 ACK'])
        except BaseException as exc:
            errors.append(type(exc).__name__)
        finally:
            server.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        with pytest.raises(CallRejected) as caught:
            peer.dial(number, media)
        assert caught.value.code == 403
        assert str(caught.value) == 'chamada SIP rejeitada: 403'
        thread.join(3)
        assert not errors
        assert observed == [True, True, True]
        assert media.address is None
    finally:
        client.close()
        media.close()
        thread.join(3)


@pytest.mark.parametrize('number', ['1234567890123456', '5511900001111\r\nX: y',
                                  'sip:5511900001111@external.invalid'])
def test_invalid_did_never_writes_to_transport(number):
    from lab.srtp_media import SrtpMedia
    client, server = socket.socketpair()
    peer, media = peer_on(client), SrtpMedia()
    try:
        with pytest.raises(ValueError, match='destino'):
            peer.dial(number,media)
        server.settimeout(0.02)
        with pytest.raises(socket.timeout):
            server.recv(1)
    finally:
        client.close()
        server.close()
        media.close()


@pytest.mark.parametrize('malformed_status', [401,403])
def test_malformed_rejection_without_to_tag_cannot_prove_did_is_blocked(malformed_status):
    from lab.srtp_media import SrtpMedia
    client,server = socket.socketpair()
    client.settimeout(2)
    server.settimeout(2)
    peer,media = peer_on(client),SrtpMedia()
    errors = []

    def serve():
        try:
            _,initial,_ = read_message(server)
            challenge = response(initial,401,
                'WWW-Authenticate: Digest realm="asterisk", nonce="private", qop="auth"')
            if malformed_status == 401:
                challenge = challenge.replace(b';tag=asterisk',b'')
            server.sendall(challenge)
            try:
                read_message(server)  # ACK caso o cliente aceite o desafio inválido.
            except ConnectionError:
                return
            _,authenticated,_ = read_message(server)
            rejected = response(authenticated,403)
            if malformed_status == 403:
                rejected = rejected.replace(b';tag=asterisk',b'')
            server.sendall(rejected)
            try:
                read_message(server)
            except ConnectionError:
                pass
        except BaseException as exc:
            errors.append(type(exc).__name__)
        finally:
            server.close()

    thread = threading.Thread(target=serve,daemon=True)
    thread.start()
    try:
        with pytest.raises(ValueError,match='tag'):
            peer.dial('5511900009999',media)
    finally:
        peer.close()
        media.close()
        thread.join(3)
    assert not thread.is_alive()
    assert not errors
