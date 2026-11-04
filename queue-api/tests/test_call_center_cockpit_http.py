"""Aceite HTTP real do cockpit: perfis, CORS, tenant e não vazamento."""
import hashlib
import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import pytest
import server
from queue_state import QueueStateTracker
from extension_states import ExtensionStateTracker

TOKENS = {
    "agent": "A" * 48,
    "supervisor_t1": "S" * 48,
    "supervisor_t2": "R" * 48,
}
ORIGIN = "https://painel.example.invalid"


def _request(port, *, token=None, path="/api/supervision/cockpit", origin=None):
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    if origin is not None:
        headers["Origin"] = origin
    client = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        client.request("GET", path, headers=headers)
        response = client.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        client.close()


class EmptyLog:
    def list(self, **kwargs):
        return []


class SLA:
    def snapshot(self):
        return {
            "fila-t1": {"offered": 10, "within_sla": 8},
            "fila-t2": {"offered": 10, "within_sla": 2},
        }


class NoPause:
    def snapshot(self):
        return {}


@pytest.fixture
def http_cockpit(tmp_path, monkeypatch):
    access = tmp_path / "queue-access.json"
    access.write_text(json.dumps({"credentials": [
        {
            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "tenant": tenant, "role": role, "expires_at": 4102444800,
            **({"extension": "t1-recepcao"} if role == "agent" else {}),
        }
        for token, tenant, role in [
            (TOKENS["agent"], "t1", "agent"),
            (TOKENS["supervisor_t1"], "t1", "supervisor"),
            (TOKENS["supervisor_t2"], "t2", "supervisor"),
        ]
    ]}), encoding="utf-8")
    access.chmod(0o600)
    tracker = QueueStateTracker()
    for queue, channel in [
        ("fila-t1", "Local/t1-private"),
        ("fila-t2", "Local/t2-private"),
    ]:
        tracker.apply_event({
            "Event": "QueueCallerJoin", "Queue": queue,
            "Channel": channel, "Uniqueid": channel.replace("/", "."),
            "CallerIDNum": "PRIVATE-" + channel,
        })
    monkeypatch.setattr(server, "QUEUE_ACCESS_POLICY_PATH", str(access))
    monkeypatch.setattr(server, "QUEUE_CORS_ORIGINS", {ORIGIN})
    monkeypatch.setattr(server, "state", tracker)
    monkeypatch.setattr(server, "extension_states", ExtensionStateTracker())
    monkeypatch.setattr(server, "queue_sla_tracker", SLA())
    monkeypatch.setattr(server, "missed_calls_log", EmptyLog())
    monkeypatch.setattr(server, "fraud_alerts_log", EmptyLog())
    monkeypatch.setattr(server, "quality_log", EmptyLog())
    monkeypatch.setattr(server, "agent_pause_store", NoPause())
    monkeypatch.setattr(server, "load_presence", lambda path: {})
    http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        yield http.server_address[1]
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=4)


def test_requires_bearer_and_does_not_expose_pii(http_cockpit):
    code, headers, body = _request(http_cockpit)
    assert code == 401
    assert headers["Cache-Control"] == "no-store"
    assert "Access-Control-Allow-Origin" not in headers
    assert b"PRIVATE-" not in body


def test_agent_cannot_use_supervisor_cockpit(http_cockpit):
    code, _, body = _request(http_cockpit, token=TOKENS["agent"])
    assert code == 403
    assert b"PRIVATE-" not in body


def test_supervisors_receive_exactly_50_indicators_and_tenant_scoped_data(http_cockpit):
    for tenant, token, expected_sla in [
        ("t1", TOKENS["supervisor_t1"], 80.0),
        ("t2", TOKENS["supervisor_t2"], 20.0),
    ]:
        code, headers, raw = _request(
            http_cockpit, token=token, path="/api/supervision/cockpit?tenant=other",
            origin=ORIGIN,
        )
        assert code == 200
        assert headers["Access-Control-Allow-Origin"] == ORIGIN
        assert headers["Cache-Control"] == "no-store"
        result = json.loads(raw)
        assert result["tenant"] == tenant
        assert result["metric_count"] == 50
        by_key = {m["key"]: m["value"] for m in result["metrics"]}
        assert by_key["aguardando"] == 1
        assert by_key["sla_percentual"] == expected_sla
        assert "PRIVATE" not in raw.decode()


@pytest.mark.parametrize("origin", ["null", "https://attacker.invalid"])
def test_origin_denylist_default(http_cockpit, origin):
    code, headers, body = _request(http_cockpit, token=TOKENS["supervisor_t1"],
                                   origin=origin)
    assert code == 403
    assert "Access-Control-Allow-Origin" not in headers
    assert b"metrics" not in body


def test_invalid_route_does_not_expose_metrics(http_cockpit):
    code, _, _ = _request(http_cockpit, token=TOKENS["supervisor_t1"],
                          path="/api/supervision/cockpitXYZ")
    assert code == 404
