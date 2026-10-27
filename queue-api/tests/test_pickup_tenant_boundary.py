"""Isolamento fail-closed do pickup dirigido, incluindo HTTP real em loopback.

O operador informa um ramal da allowlist, mas o tenant da fila é lido
somente do rastreador AMI, nunca do JSON de quem solicita o pickup.
"""
import hashlib
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import server
from pickup import pickup_matches_queue
from queue_state import QueueStateTracker


@pytest.mark.parametrize(("extension", "queue", "allowed"), [
    ("t1-recepcao", "fila-t1", True),
    ("t1-recepcao-2", "fila-t1-en", True),
    ("t2-recepcao", "fila-t2-es", True),
    ("t10-recepcao", "fila-t10", True),
    ("t1-recepcao", "fila-t2", False),
    ("t1-recepcao", "fila-t10", False),
    ("t10-recepcao", "fila-t1", False),
    ("t1-recepcao", "fila-t1-not-valid", False),
    ("t1-recepcao", "fila-t1-en-extra", False),
    ("t1-recepcao", "fila-t1\\n", False),
    ("t01-recepcao", "fila-t1", False),
    ("t1-recepcao", "", False),
    ("t1-recepcao", None, False),
    (None, "fila-t1", False),
    (123, "fila-t1", False),
    ("t1-recepcao", 123, False),
])
def test_queue_and_extension_tenants_must_match_exactly(extension, queue, allowed):
    assert pickup_matches_queue(extension, queue) is allowed


@pytest.fixture
def pickup_http(tmp_path, monkeypatch):
    tracker = QueueStateTracker()
    class AMISpy:
        def __init__(self):
            self.calls = []

        def redirect_channel(self, channel, context, exten):
            self.calls.append((channel, context, exten))
            return {"Response": "Success"}

    mock_ami = AMISpy()
    credentials = []
    for tenant, token in [("t1", "Q"*48), ("t2", "R"*48), ("t10", "T"*48)]:
        credentials.append({
            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "tenant": tenant, "role": "supervisor", "expires_at": 4102444800,
        })
    policy_file = tmp_path / "queue-access.json"
    policy_file.write_text(json.dumps({"credentials": credentials}))
    policy_file.chmod(0o600)
    monkeypatch.setattr(server, "QUEUE_ACCESS_POLICY_PATH", str(policy_file))
    monkeypatch.setattr(server, "QUEUE_CORS_ORIGINS", {"http://localhost:8082"})
    monkeypatch.setattr(server, "ami", mock_ami)
    monkeypatch.setattr(server, "state", tracker)
    monkeypatch.setattr(
        server, "PICKUP_ALLOWED_EXTENSIONS",
        ["t1-recepcao", "t2-recepcao", "t10-recepcao"],
    )
    http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:{}".format(http.server_address[1]), tracker, mock_ami
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=3)


def pickup(base, channel, extension, *, token="Q"*48, **extra):
    raw = json.dumps({"channel": channel, "extension": extension, **extra}).encode()
    request = urllib.request.Request(
        base + "/api/queue/pickup", data=raw, method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + token,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def join(tracker, channel, queue):
    tracker.apply_event({
        "Event": "QueueCallerJoin", "Queue": queue, "Channel": channel,
    })


def test_real_http_rejects_cross_tenant_and_never_calls_ami(pickup_http):
    base, tracker, ami = pickup_http
    join(tracker, "CH2", "fila-t2")
    status, _ = pickup(base, "CH2", "t1-recepcao")
    assert status == 403
    assert ami.calls == []
    assert [r["channel"] for r in tracker.waiting_list()] == ["CH2"]


def test_real_http_rejects_prefix_collision_t1_and_t10(pickup_http):
    base, tracker, ami = pickup_http
    join(tracker, "CH10", "fila-t10")
    assert pickup(base, "CH10", "t1-recepcao")[0] == 403
    assert ami.calls == []
    assert pickup(base, "CH10", "t10-recepcao", token="T"*48)[0] == 200
    assert ami.calls == [("CH10", server.PICKUP_CONTEXT, "t10-recepcao")]


def test_real_http_accepts_same_tenant_and_removes_only_successful_channel(pickup_http):
    base, tracker, ami = pickup_http
    join(tracker, "A", "fila-t1-en")
    join(tracker, "B", "fila-t2")
    status, body = pickup(base, "A", "t1-recepcao")
    assert status == 200 and body["ok"] is True
    assert ami.calls == [("A", server.PICKUP_CONTEXT, "t1-recepcao")]
    assert [r["channel"] for r in tracker.waiting_list()] == ["B"]


def test_real_http_rejects_stale_channel_and_untrusted_queue_json(pickup_http):
    base, tracker, ami = pickup_http
    join(tracker, "A", "fila-t2")
    assert pickup(base, "A", "t1-recepcao", queue="fila-t1")[0] == 403
    tracker.apply_event({"Event": "QueueCallerLeave", "Channel": "A"})
    assert pickup(base, "A", "t2-recepcao")[0] == 403
    assert pickup(base, "missing", "t1-recepcao")[0] == 403
    assert ami.calls == []


def test_real_http_fails_closed_for_invalid_ami_queue(pickup_http):
    base, tracker, ami = pickup_http
    join(tracker, "A", "fila-t1-malformed")
    assert pickup(base, "A", "t1-recepcao")[0] == 403
    assert ami.calls == []


def test_amitracker_returns_queue_for_only_known_channels():
    tracker = QueueStateTracker()
    join(tracker, "A", "fila-t1")
    assert tracker.queue_for_channel("A") == "fila-t1"
    assert tracker.queue_for_channel("B") is None
    assert tracker.queue_for_channel(None) is None
    tracker.apply_event({"Event": "Hangup", "Channel": "A"})
    assert tracker.queue_for_channel("A") is None
