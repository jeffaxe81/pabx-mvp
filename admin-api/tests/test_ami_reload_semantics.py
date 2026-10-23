"""Regressões de Command Follows: sucesso do AMI != sucesso do CLI."""
import pytest

import ami_client
from ami_client import AMIClient
from ami_reload_policy import cli_reload_output_failed


ACTION_ID = "axe-pabx-" + "a" * 24
COMPONENTS = ("pjsip", "dialplan", "voicemail", "queue", "parking")


class FakeSocket:
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.sent = []

    def sendall(self, data):
        self.sent.append(data)

    def recv(self, n):
        return self.chunks.pop(0) if self.chunks else b""


def build_client(chunks, monkeypatch):
    monkeypatch.setattr(ami_client.secrets, "token_hex", lambda n: "a" * (n * 2))
    client = AMIClient("127.0.0.1", 5038, "admin-api", "test-only")
    client._sock = FakeSocket(chunks)
    return client


def follows(output):
    return (
        f"Response: Follows\r\nActionID: {ACTION_ID}\r\n"
        f"Output: {output}\r\nOutput: --END COMMAND--\r\n\r\n"
    ).encode("utf-8")


def test_cli_policy_detects_explicit_failures_not_informational_messages():
    for failure in (
        "No such command 'pjsip reload'",
        "Unknown command 'dialplan reload'",
        "Command 'parking reload' failed",
        "Unable to reload PJSIP configuration",
        "Failed to load module res_pjsip.so",
        "Error reloading module",
    ):
        assert cli_reload_output_failed(failure), failure
    for success in (
        "PJSIP configuration reloaded.",
        "Reload complete. 0 errors.",
        "No errors were detected.",
        "",
    ):
        assert not cli_reload_output_failed(success), success


def test_reload_stops_on_follows_no_such_command(monkeypatch):
    client = build_client([follows("No such command 'pjsip reload'")], monkeypatch)
    with pytest.raises(ConnectionError, match="pjsip"):
        client.reload_pjsip_and_dialplan()
    assert len(client._sock.sent) == 1
    assert b"Command: pjsip reload\r\n" in client._sock.sent[0]


def test_reload_fails_on_second_component_without_issuing_remaining(monkeypatch):
    client = build_client([
        follows("PJSIP Reloaded") + follows("Unable to reload dialplan")
    ], monkeypatch)
    with pytest.raises(ConnectionError, match="dialplan"):
        client.reload_pjsip_and_dialplan()
    assert len(client._sock.sent) == 2
    assert b"Command: dialplan reload\r\n" in client._sock.sent[1]


def test_reload_accepts_valid_follows_outputs_and_returns_status_only(monkeypatch):
    response = b"".join(follows(f"{c} configuration reloaded.") for c in COMPONENTS)
    client = build_client([response], monkeypatch)
    result = client.reload_pjsip_and_dialplan()
    assert result == {component: "Follows" for component in COMPONENTS}
    assert "_cli_output" not in result
    assert len(client._sock.sent) == 5


def test_fragmented_follows_cli_error_is_detected_and_followup_frame_preserved(monkeypatch):
    first = (
        f"Response: Follows\r\nActionID: {ACTION_ID}\r\n\r\n"
        "Output: No such command 'pjsip reload'\r\n"
        "Output: --END COMMAND--\r\n\r\n"
    ).encode()
    subsequent = (
        f"Response: Success\r\nActionID: {ACTION_ID}\r\n\r\n"
    ).encode()
    client = build_client([first[:40], first[40:78], first[78:] + subsequent], monkeypatch)
    with pytest.raises(ConnectionError, match="pjsip"):
        client.reload_pjsip_and_dialplan()
    assert client._send_action({"Action": "Ping"})["Response"] == "Success"


def test_reload_rejects_ami_response_error_without_disclosing_output(monkeypatch):
    failure = (
        f"Response: Error\r\nActionID: {ACTION_ID}\r\n"
        "Message: Private data from server\r\n\r\n"
    ).encode()
    client = build_client([failure], monkeypatch)
    with pytest.raises(ConnectionError, match="pjsip") as raised:
        client.reload_pjsip_and_dialplan()
    assert "Private data" not in str(raised.value)


def test_cli_output_cannot_grow_unbounded(monkeypatch):
    from ami_client import MAX_AMI_REPLY_BYTES
    response = (
        f"Response: Follows\r\nActionID: {ACTION_ID}\r\n\r\n"
    ).encode()
    pieces = [response] + [b"x" * 4096] * (MAX_AMI_REPLY_BYTES // 4096 + 2)
    client = build_client(pieces, monkeypatch)
    with pytest.raises(ConnectionError, match="limite"):
        client.reload_pjsip_and_dialplan()
