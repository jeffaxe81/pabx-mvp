"""HTTP real: isolamento do relatório SLA entre t1, t2 e t10.

Único servidor loopback, AMI simulado por eventos; não usa dados de
clientes nem faz chamadas externas. Testa a Handler HTTP efetiva.
"""
import hashlib
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest
import server
from queue_sla import QueueSLATracker, SLAHistoryStore

TENANTS = ("t1", "t2", "t10")
TOKENS = {tenant: (chr(65 + pos) * 48) for pos, tenant in enumerate(TENANTS)}
ORIGIN = "https://console.axe-lab.invalid"


@pytest.fixture
def sla_api(tmp_path, monkeypatch):
    policy_path = tmp_path / "queue_policy.json"
    policy_path.write_text(json.dumps({"credentials": [
        {"tenant": t, "role": "supervisor",
         "token_sha256": hashlib.sha256(TOKENS[t].encode("ascii")).hexdigest(),
         "expires_at": 4102444800}
        for t in TENANTS
    ]}), encoding="utf-8")
    policy_path.chmod(0o600)

    clock = lambda: 1761600000.0
    tracker = QueueSLATracker(threshold_seconds=20, clock=clock)
    for tenant, hold in (("t1", "12"), ("t2", "45"), ("t10", "20")):
        tracker.apply_event({"Event": "AgentConnect",
                             "Queue": "fila-" + tenant, "HoldTime": hold})
    tracker.apply_event({"Event": "QueueCallerAbandon",
                         "Queue": "fila-t1", "HoldTime": "2"})
    tracker.apply_event({"Event": "AgentConnect",
                         "Queue": "fila-t10"})  # sem HoldTime, não ganha SLA
    history = SLAHistoryStore(tmp_path / "history.jsonl")
    for tenant in TENANTS:
        history.append({"queue": "fila-" + tenant, "date": "2026-10-27",
                        "offered": 3, "within_sla": 1,
                        "sla_percent": 33.3})
    monkeypatch.setattr(server, "queue_sla_tracker", tracker)
    monkeypatch.setattr(server, "sla_history_store", history)
    monkeypatch.setattr(server, "QUEUE_ACCESS_POLICY_PATH", str(policy_path))
    monkeypatch.setattr(server, "QUEUE_CORS_ORIGINS", {ORIGIN})

    http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{http.server_address[1]}"
    finally:
        http.shutdown()
        http.server_close()
        worker.join(timeout=4)


def call(url, path, token=None, origin=None):
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    if origin:
        headers["Origin"] = origin
    req = urllib.request.Request(url + path, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=4) as response:
            return response.status, dict(response.headers), json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), json.loads(error.read())


@pytest.mark.parametrize("tenant", TENANTS)
def test_current_sla_http_isolation_even_with_query_tenant_spoofing(sla_api, tenant):
    other = next(t for t in TENANTS if t != tenant)
    status, headers, body = call(
        sla_api, "/api/metrics/sla?tenant=" + other, TOKENS[tenant], ORIGIN)
    assert status == 200
    assert headers["Cache-Control"] == "no-store"
    assert headers["Access-Control-Allow-Origin"] == ORIGIN
    assert list(body["queues"]) == ["fila-" + tenant]
    assert "fila-" + other not in body["queues"]
    assert body["threshold_seconds"] == 20
    expected = {"t1": 50.0, "t2": 0.0, "t10": 50.0}
    assert body["queues"]["fila-" + tenant]["sla_percent"] == expected[tenant]


@pytest.mark.parametrize("tenant", TENANTS)
def test_historical_sla_http_isolation_and_date_filter(sla_api, tenant):
    other = next(t for t in TENANTS if t != tenant)
    url = "/api/metrics/sla/history?tenant=" + other + "&start=2026-10-27&end=2026-10-27"
    status, _, body = call(sla_api, url, TOKENS[tenant])
    assert status == 200
    assert list(body["by_date"]) == ["2026-10-27"]
    assert list(body["by_date"]["2026-10-27"]) == ["fila-" + tenant]
    assert body["by_date"]["2026-10-27"]["fila-" + tenant]["sla_percent"] == 33.3
    assert call(sla_api, "/api/metrics/sla/history?start=2026-10-28",
                TOKENS[tenant])[2]["by_date"] == {}


@pytest.mark.parametrize("path", ["/api/metrics/sla", "/api/metrics/sla/history"])
def test_sla_reports_require_bearer_and_reject_foreign_origin(sla_api, path):
    assert call(sla_api, path)[0] == 401
    status, headers, _ = call(sla_api, path, TOKENS["t1"], "https://evil.invalid")
    assert status == 403
    assert "Access-Control-Allow-Origin" not in headers
    assert call(sla_api, path, "Z" * 48)[0] == 401
