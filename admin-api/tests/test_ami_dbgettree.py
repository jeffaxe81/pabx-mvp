"""DBGetTree: respostas completas, isolamento por família e evento final."""
import pytest

import ami_client
from ami_client import AMIClient


ACTION_ID = "axe-pabx-" + "b" * 24


class FakeSocket:
    def __init__(self, data):
        self.parts = list(data)
        self.sent = []
        self.timeout_changes = []

    def sendall(self, data):
        self.sent.append(data)

    def recv(self, size):
        return self.parts.pop(0) if self.parts else b""

    def settimeout(self, timeout):
        self.timeout_changes.append(timeout)


def message(*lines):
    return ("\r\n".join(lines) + "\r\n\r\n").encode("utf-8")


def reply():
    return message("Response: Success", "EventList: start", "ActionID: " + ACTION_ID)


def entry(key, val, event="DBGetTreeResponse", action_id=ACTION_ID):
    return message("Event: " + event, "ActionID: " + action_id,
                   "Key: " + key, "Val: " + val)


def completed():
    return message("Event: DBGetTreeComplete", "ActionID: " + ACTION_ID,
                   "EventList: Complete", "ListItems: 2")


def build_client(packets, monkeypatch):
    monkeypatch.setattr(ami_client.secrets, "token_hex", lambda n: "b" * (n * 2))
    client = AMIClient("127.0.0.1", 5038, "admin-api", "local-secret")
    client._sock = FakeSocket(packets)
    return client


def test_vips_read_until_completion_without_timeout_wait(monkeypatch):
    frames = [
        reply(),
        entry("/vip-t1/551199998888", "1100"),
        entry("/vip-t1/551199998887", "1101"),
        completed(),
    ]
    client = build_client([b"".join(frames[:3]), frames[3]], monkeypatch)
    assert client.list_vips("t1") == [
        {"number": "551199998888", "target_extension": "1100"},
        {"number": "551199998887", "target_extension": "1101"},
    ]
    assert b"Family: vip-t1\r\n" in client._sock.sent[0]
    assert client._sock.timeout_changes == []


def test_blocked_numbers_return_only_requested_tenant(monkeypatch):
    data = (
        reply() + entry("/blocklist-t1/55118880000", "1")
        + entry("/blocklist-t2/55117770000", "1")
        + completed()
    )
    client = build_client([data[:43], data[43:]], monkeypatch)
    assert client.list_blocked_numbers("t1") == ["55118880000"]


def test_overflow_timeout_returns_value_from_exact_tenant_key(monkeypatch):
    data = reply() + entry("/config-t1/overflow-timeout-segundos", "67") + completed()
    client = build_client([data], monkeypatch)
    assert client.get_overflow_timeout("t1") == "67"


def test_missing_overflow_key_returns_none_after_completion(monkeypatch):
    data = reply() + entry("/config-t1/modo-feriado", "1") + completed()
    client = build_client([data], monkeypatch)
    assert client.get_overflow_timeout("t1") is None


def test_empty_list_needs_explicit_completion(monkeypatch):
    client = build_client([reply(), completed()], monkeypatch)
    assert client.list_blocked_numbers("t1") == []


def test_missing_complete_or_closed_connection_fails_closed(monkeypatch):
    client = build_client([reply(), entry("/vip-t1/1", "1100")], monkeypatch)
    with pytest.raises(ConnectionError, match="fechou"):
        client.list_vips("t1")


def test_unrelated_event_ignored_until_matching_complete(monkeypatch):
    unrelated = entry("/vip-t9/1", "1111", action_id="axe-pabx-unrelated")
    client = build_client([
        reply() + unrelated + entry("/vip-t1/2", "1101") + completed()
    ], monkeypatch)
    assert client.list_vips("t1") == [{"number": "2", "target_extension": "1101"}]


def test_wrong_event_for_matching_action_fails_closed(monkeypatch):
    bad = message("Event: ChannelCreate", "ActionID: " + ACTION_ID)
    client = build_client([reply() + bad], monkeypatch)
    with pytest.raises(ConnectionError, match="inesperado"):
        client.list_vips("t1")


def test_error_response_cannot_be_treated_as_empty_list(monkeypatch):
    failure = message("Response: Error", "ActionID: " + ACTION_ID,
                      "Message: Authentication required")
    client = build_client([failure], monkeypatch)
    with pytest.raises(ConnectionError, match="não autorizada"):
        client.list_blocked_numbers("t1")


def test_action_after_list_uses_buffered_response_and_lock(monkeypatch):
    data = reply() + completed() + message("Response: Success", "ActionID: " + ACTION_ID)
    client = build_client([data], monkeypatch)
    assert client.list_vips("t1") == []
    assert client._send_action({"Action": "Ping"})["Response"] == "Success"
    assert len(client._sock.sent) == 2
    assert client._sock.timeout_changes == []
