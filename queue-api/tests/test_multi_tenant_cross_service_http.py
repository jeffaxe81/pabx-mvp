"""Integração HTTP conjunta de isolamento multiempresa: filas + gravações.

Executa a Handler real em loopback com dois catálogos independentes.
Nenhuma rede externa, Asterisk, ligação ou arquivo de cliente é usado.
Este aceite NÃO comprova isolamento de volumes ou roteamento em produção.
"""
import hashlib
import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import pytest

import server
from queue_state import QueueStateTracker

TENANTS = ("t1", "t2", "t10")
QUEUE_TOKEN = {t: chr(65 + i) * 48 for i, t in enumerate(TENANTS)}
RECORDING_TOKEN = {t: chr(80 + i) * 48 for i, t in enumerate(TENANTS)}
ORIGIN = "https://console.axe-lab.invalid"


def _credential(tenant, token):
    return {
        "token_sha256": hashlib.sha256(token.encode("ascii")).hexdigest(),
        "tenant": tenant, "role": "supervisor", "expires_at": 4102444800,
    }


def _http(port, method, path, token=None, *, origin=None, payload=None):
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    if origin is not None:
        headers["Origin"] = origin
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request(method, path, body=body, headers=headers)
        result = conn.getresponse()
        return result.status, dict(result.getheaders()), result.read()
    finally:
        conn.close()


@pytest.fixture
def service_boundary(tmp_path, monkeypatch):
    root = tmp_path / "recordings"
    root.mkdir()
    recordings = {}
    for tenant in TENANTS:
        filename = tenant + "-private.wav"
        (root / filename).write_bytes(("PRIVATE AUDIO " + tenant).encode())
        recordings[filename] = {"tenant": tenant, "owner_extension": tenant + "-recepcao"}

    qpolicy = tmp_path / "queue-access.json"
    qpolicy.write_text(json.dumps({"credentials": [
        _credential(t, QUEUE_TOKEN[t]) for t in TENANTS
    ]}), encoding="utf-8")
    qpolicy.chmod(0o600)
    rpolicy = tmp_path / "recording-access.json"
    rpolicy.write_text(json.dumps({
        "credentials": [_credential(t, RECORDING_TOKEN[t]) for t in TENANTS],
        "recordings": recordings,
    }), encoding="utf-8")
    rpolicy.chmod(0o600)

    tracker = QueueStateTracker()
    for tenant in TENANTS:
        tracker.apply_event({
            "Event": "QueueCallerJoin",
            "Queue": "fila-" + tenant,
            "Channel": "Local/" + tenant + "-private",
            "CallerIDNum": tenant + "-private",
        })

    class NoTelephony:
        def __init__(self):
            self.actions = []
        def redirect_channel(self, *args, **kwargs):
            self.actions.append((args, kwargs))
            raise AssertionError("cross-tenant pickup must not reach AMI")

    spy = NoTelephony()
    monkeypatch.setattr(server, "state", tracker)
    monkeypatch.setattr(server, "ami", spy)
    monkeypatch.setattr(server, "QUEUE_ACCESS_POLICY_PATH", str(qpolicy))
    monkeypatch.setattr(server, "RECORDINGS_ACCESS_POLICY_PATH", str(rpolicy))
    monkeypatch.setattr(server, "RECORDINGS_DIR", str(root))
    monkeypatch.setattr(server, "QUEUE_CORS_ORIGINS", {ORIGIN})
    monkeypatch.setattr(server, "RECORDINGS_CORS_ORIGINS", {ORIGIN})
    monkeypatch.setattr(server, "PICKUP_ALLOWED_EXTENSIONS",
                        [t + "-recepcao" for t in TENANTS])

    http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        yield http.server_address[1], spy, rpolicy
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=4)


@pytest.mark.parametrize("tenant", TENANTS)
def test_only_own_queue_and_recordings_visible_even_with_spoofed_tenant(
    service_boundary, tenant
):
    port, _, _ = service_boundary
    other = next(t for t in TENANTS if t != tenant)
    status, _, body = _http(
        port, "GET", "/api/queue?tenant=" + other,
        QUEUE_TOKEN[tenant], origin=ORIGIN,
    )
    assert status == 200
    waiting = json.loads(body)["waiting"]
    assert len(waiting) == 1
    assert waiting[0]["queue"] == "fila-" + tenant
    assert all(t.encode() not in body for t in (
        other + "-private", "fila-" + other,
    ))

    status, _, body = _http(
        port, "GET", "/api/recordings?tenant=" + other,
        RECORDING_TOKEN[tenant], origin=ORIGIN,
    )
    assert status == 200
    names = {item["filename"] for item in json.loads(body)["recordings"]}
    assert names == {tenant + "-private.wav"}
    assert other.encode() + b"-private.wav" not in body


@pytest.mark.parametrize("tenant", TENANTS)
def test_queue_and_recording_tokens_not_interchangeable(service_boundary, tenant):
    port, _, _ = service_boundary
    assert _http(port, "GET", "/api/queue", RECORDING_TOKEN[tenant])[0] == 401
    assert _http(port, "GET", "/api/recordings", QUEUE_TOKEN[tenant])[0] == 401


@pytest.mark.parametrize("tenant", TENANTS)
@pytest.mark.parametrize("target", TENANTS)
def test_recording_download_scoped_to_exact_tenant(service_boundary, tenant, target):
    port, _, _ = service_boundary
    status, _, body = _http(
        port, "GET", "/recordings/" + target + "-private.wav",
        RECORDING_TOKEN[tenant],
    )
    if target == tenant:
        assert status == 200
        assert body == ("PRIVATE AUDIO " + tenant).encode()
    else:
        assert status == 404
        assert b"PRIVATE AUDIO" not in body


@pytest.mark.parametrize("tenant", TENANTS)
def test_cross_tenant_queue_pickup_does_not_reach_ami(service_boundary, tenant):
    port, spy, _ = service_boundary
    other = next(t for t in TENANTS if t != tenant)
    status, _, _ = _http(
        port, "POST", "/api/queue/pickup", QUEUE_TOKEN[tenant],
        payload={"channel": "Local/" + other + "-private",
                 "extension": tenant + "-recepcao",
                 "queue": "fila-" + tenant},
    )
    assert status == 403
    assert spy.actions == []


@pytest.mark.parametrize("tenant", TENANTS)
def test_origin_restriction_applies_to_both_services(service_boundary, tenant):
    port, _, _ = service_boundary
    for path, token in (
        ("/api/queue", QUEUE_TOKEN[tenant]),
        ("/api/recordings", RECORDING_TOKEN[tenant]),
    ):
        status, headers, _ = _http(
            port, "GET", path, token, origin="https://intruder.invalid"
        )
        assert status == 403
        assert "Access-Control-Allow-Origin" not in headers
        status, headers, _ = _http(port, "GET", path, token, origin=ORIGIN)
        assert status == 200
        assert headers.get("Access-Control-Allow-Origin") == ORIGIN


def test_policy_revocation_denies_recordings_without_restarting_server(service_boundary):
    port, _, rpolicy = service_boundary
    assert _http(port, "GET", "/api/recordings", RECORDING_TOKEN["t1"])[0] == 200
    original = json.loads(rpolicy.read_text())
    original["credentials"] = [entry for entry in original["credentials"]
                               if entry["tenant"] != "t1"]
    rpolicy.write_text(json.dumps(original))
    assert _http(port, "GET", "/api/recordings", RECORDING_TOKEN["t1"])[0] == 401
    assert _http(port, "GET", "/api/recordings", RECORDING_TOKEN["t2"])[0] == 200
