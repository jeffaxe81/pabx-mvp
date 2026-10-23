"""Testes de stream AMI com TCP fragmentado, eventos e ActionID."""
import socket

import pytest

import ami_client
from ami_client import AMIClient, MAX_AMI_REPLY_BYTES


ACTION_ID = "axe-pabx-" + ("a" * 24)


class FakeSocket:
    def __init__(self, pieces):
        self.pieces = list(pieces)
        self.sent = []
        self.closed = False

    def recv(self, size):
        item = self.pieces.pop(0) if self.pieces else b""
        if isinstance(item, BaseException):
            raise item
        return item

    def sendall(self, data):
        self.sent.append(data)

    def close(self):
        self.closed = True


def client_with(pieces, monkeypatch):
    monkeypatch.setattr(ami_client.secrets, "token_hex", lambda n: "a" * (n * 2))
    client = AMIClient("127.0.0.1", 5038, "admin-api", "secret-value")
    client._sock = FakeSocket(pieces)
    return client


def test_fragmented_ami_response_is_assembled_before_success(monkeypatch):
    client = client_with([
        b"Res", b"ponse: Succ", b"ess\r\nActionID: axe-pabx-" + b"a" * 24,
        b"\r\nMessage: OK\r\n", b"\r\n",
    ], monkeypatch)
    assert client._send_action({"Action": "Ping"})["Response"] == "Success"
    assert ACTION_ID.encode() in client._sock.sent[0]


def test_multiple_messages_one_recv_do_not_lose_second_response(monkeypatch):
    packet = (
        f"Response: Success\r\nActionID: {ACTION_ID}\r\n\r\n"
        f"Response: Error\r\nActionID: {ACTION_ID}\r\n\r\n"
    ).encode()
    client = client_with([packet], monkeypatch)
    assert client._send_action({"Action": "Ping"})["Response"] == "Success"
    assert client._send_action({"Action": "Ping"})["Response"] == "Error"
    assert len(client._sock.sent) == 2


def test_interleaved_event_is_ignored_before_matching_response(monkeypatch):
    packet = (
        "Event: PeerStatus\r\nPeer: t1-1001\r\n\r\n"
        f"Response: Success\r\nActionID: {ACTION_ID}\r\n\r\n"
    ).encode()
    client = client_with([packet], monkeypatch)
    assert client._send_action({"Action": "DBPut"})["Response"] == "Success"


def test_mismatched_action_id_fails_closed(monkeypatch):
    client = client_with([b"Response: Success\r\nActionID: someone-else\r\n\r\n"], monkeypatch)
    with pytest.raises(ConnectionError, match="n\u00e3o corresponde"):
        client._send_action({"Action": "DBPut"})


def test_truncated_packet_and_socket_timeout_fail_closed(monkeypatch):
    for chunks in (
        [b"Response: Success\r\nActionID: ", b""],
        [socket.timeout("simulated timeout")],
    ):
        client = client_with(chunks, monkeypatch)
        with pytest.raises((ConnectionError, socket.timeout)):
            client._send_action({"Action": "Ping"})


def test_oversized_ami_reply_fails_without_unbounded_buffer(monkeypatch):
    pieces = [b"x" * 4096] * (MAX_AMI_REPLY_BYTES // 4096 + 1)
    client = client_with(pieces, monkeypatch)
    with pytest.raises(ConnectionError, match="limite"):
        client._send_action({"Action": "Ping"})


def test_login_banner_fragmented_preserves_extra_packet_bytes(monkeypatch):
    packets = [
        b"Asterisk Call Man",
        b"ager/5.0\r\nResponse: Succ",
        f"ess\r\nActionID: {ACTION_ID}\r\n\r\n".encode(),
    ]
    client = client_with(packets, monkeypatch)
    fake = client._sock
    monkeypatch.setattr(ami_client.socket, "create_connection",
                        lambda *args, **kwargs: fake)
    client.connect_and_login()
    assert b"Action: Login\r\n" in fake.sent[0]
    assert b"Secret: secret-value\r\n" in fake.sent[0]
    assert not fake.closed


def test_login_fails_without_valid_banner_and_closes_socket(monkeypatch):
    client = client_with([b"NOPE\r\n"], monkeypatch)
    fake = client._sock
    monkeypatch.setattr(ami_client.socket, "create_connection",
                        lambda *args, **kwargs: fake)
    with pytest.raises(ConnectionError, match="Banner"):
        client.connect_and_login()
    assert fake.closed


def test_login_denied_without_echoing_server_or_secret(monkeypatch):
    fake_data = (
        b"Asterisk Call Manager/5.0\r\n"
        + f"Response: Error\r\nActionID: {ACTION_ID}\r\n".encode()
        + b"Message: private-secret\r\n\r\n"
    )
    client = client_with([fake_data], monkeypatch)
    fake = client._sock
    monkeypatch.setattr(ami_client.socket, "create_connection",
                        lambda *args, **kwargs: fake)
    with pytest.raises(ConnectionError) as caught:
        client.connect_and_login()
    assert "private-secret" not in str(caught.value)
    assert "secret-value" not in str(caught.value)
    assert fake.closed


def test_old_command_follows_drain_to_terminal_marker(monkeypatch):
    response = (
        f"Response: Follows\r\nActionID: {ACTION_ID}\r\n\r\n"
        "Output: pjsip reload complete\r\n"
        "Output: --END COMMAND--\r\n\r\n"
        f"Response: Success\r\nActionID: {ACTION_ID}\r\n\r\n"
    ).encode()
    client = client_with([response[:47], response[47:71], response[71:]], monkeypatch)
    assert client._send_action({"Action": "Command", "Command": "pjsip reload"})["Response"] == "Follows"
    assert client._send_action({"Action": "Ping"})["Response"] == "Success"


def test_incomplete_old_command_output_refused(monkeypatch):
    response = f"Response: Follows\r\nActionID: {ACTION_ID}\r\n\r\n".encode()
    client = client_with([response, b"Output: not finished\r\n", b""], monkeypatch)
    with pytest.raises(ConnectionError):
        client._send_action({"Action": "Command", "Command": "pjsip reload"})


def test_full_response_before_trailer_is_still_supported(monkeypatch):
    response = (
        f"Response: Follows\r\nActionID: {ACTION_ID}\r\n"
        "Output: result\r\nOutput: --END COMMAND--\r\n\r\n"
    ).encode()
    client = client_with([response], monkeypatch)
    assert client._send_action({"Action": "Command", "Command": "dialplan reload"})["Response"] == "Follows"
