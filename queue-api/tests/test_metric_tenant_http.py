"""End-to-end loopback HTTP isolation of metrics, SLA and CDR reporting.

No external credentials, customer data or production Asterisk are used.
"""
import hashlib
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest
import server
from metrics import TenantDailyMetrics, tenant_from_cdr
from queue_sla import QueueSLATracker, SLAHistoryStore
from reports import CallLogStore

TOKENS = {"t1": "A"*48, "t2": "B"*48, "t10": "C"*48}


@pytest.fixture
def api(tmp_path, monkeypatch):
    policy_file = tmp_path / "queue_access.json"
    policy_file.write_text(json.dumps({"credentials": [{
        "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
        "tenant": tenant, "role": "supervisor", "expires_at": 4102444800,
    } for tenant, token in TOKENS.items()]}))
    policy_file.chmod(0o600)

    now = lambda: 1_700_000_000
    metrics = TenantDailyMetrics(clock=now)
    for event in [
        {"Event": "Cdr", "AccountCode": "t1", "Disposition": "ANSWERED", "BillableSeconds": "60"},
        {"Event": "Cdr", "AccountCode": "t1", "Disposition": "NO ANSWER", "BillableSeconds": "0"},
        {"Event": "Cdr", "AccountCode": "t2", "Disposition": "ANSWERED", "BillableSeconds": "240"},
        {"Event": "Cdr", "AccountCode": "t10", "Disposition": "ANSWERED", "BillableSeconds": "360"},
        {"Event": "Cdr", "Disposition": "ANSWERED", "BillableSeconds": "99999"},
        {"Event": "Cdr", "AccountCode": "t1", "Accountcode": "t2",
         "Disposition": "ANSWERED", "BillableSeconds": "99999"},
        {"Event": "Cdr", "AccountCode": "t1evil", "Disposition": "ANSWERED"},
    ]:
        metrics.apply_cdr_event(event)

    sla = QueueSLATracker(clock=now)
    for queue, wait in [
        ("fila-t1", 10), ("fila-t1-en", 35), ("fila-t2", 2),
        ("fila-t10", 4), ("fila-t1evil", 6),
    ]:
        sla.apply_event({"Event": "AgentConnect", "Queue": queue, "HoldTime": str(wait)})
    history = SLAHistoryStore(tmp_path / "sla.jsonl")
    for queue in ["fila-t1", "fila-t1-en", "fila-t2", "fila-t10", "fila-t1evil"]:
        history.append({"date": "2026-01-01", "queue": queue,
                        "offered": 3, "within_sla": 2, "sla_percent": 66.7})
    calls = CallLogStore(tmp_path / "cdr.jsonl")
    for tenant, operator in [("t1", "t1-recepcao"), ("t2", "t2-recepcao"),
                             ("t10", "t10-recepcao"), (None, "unknown")]:
        calls.append({"date": "2026-01-01", "tenant": tenant,
                      "operator": operator, "disposition": "ANSWERED",
                      "billable_seconds": 50, "caller_id_num": "secret-" + operator})
    monkeypatch.setattr(server, "tenant_daily_metrics", metrics)
    monkeypatch.setattr(server, "queue_sla_tracker", sla)
    monkeypatch.setattr(server, "sla_history_store", history)
    monkeypatch.setattr(server, "call_log_store", calls)
    monkeypatch.setattr(server, "QUEUE_ACCESS_POLICY_PATH", str(policy_file))
    monkeypatch.setattr(server, "QUEUE_CORS_ORIGINS", {"http://localhost:8082"})
    http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:{}".format(http.server_address[1]), policy_file
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=3)


def get(base, path, token=None, origin=None, method="GET"):
    headers = {}
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    if origin is not None:
        headers["Origin"] = origin
    request = urllib.request.Request(base + path, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as res:
            return res.status, dict(res.headers), res.read()
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), err.read()


def payload(result):
    return json.loads(result[2])


@pytest.mark.parametrize("path", [
    "/api/metrics/today", "/api/metrics/sla",
    "/api/metrics/sla/history", "/api/reports",
])
def test_anonymous_does_not_view_any_metric(path, api):
    base, _ = api
    result = get(base, path)
    assert result[0] == 401
    assert result[1]["Cache-Control"] == "no-store"
    assert "Access-Control-Allow-Origin" not in result[1]


def test_daily_metrics_never_reuse_global_or_wrong_tenant(api):
    base, _ = api
    one = payload(get(base, "/api/metrics/today?tenant=t2", TOKENS["t1"]))
    two = payload(get(base, "/api/metrics/today", TOKENS["t2"]))
    ten = payload(get(base, "/api/metrics/today", TOKENS["t10"]))
    assert (one["total_calls"], one["answered_calls"], one["missed_calls"]) == (2, 1, 1)
    assert one["average_talk_seconds"] == 60
    assert two["total_calls"] == 1 and two["average_talk_seconds"] == 240
    assert ten["total_calls"] == 1 and ten["average_talk_seconds"] == 360


def test_sla_current_only_own_queues_and_not_prefixes(api):
    base, _ = api
    expected = {"t1": {"fila-t1", "fila-t1-en"}, "t2": {"fila-t2"},
                "t10": {"fila-t10"}}
    for tenant, names in expected.items():
        result = get(base, "/api/metrics/sla?tenant=t2", TOKENS[tenant])
        assert result[0] == 200
        assert set(payload(result)["queues"]) == names
        assert payload(result)["threshold_seconds"] == server.SLA_THRESHOLD_SECONDS


def test_historical_sla_never_exposes_another_tenant(api):
    base, _ = api
    for tenant, allowed in [("t1", {"fila-t1", "fila-t1-en"}),
                            ("t2", {"fila-t2"}), ("t10", {"fila-t10"})]:
        result = get(base, "/api/metrics/sla/history?start=2026-01-01&tenant=t2", TOKENS[tenant])
        assert result[0] == 200
        assert set(payload(result)["by_date"]["2026-01-01"]) == allowed


def test_reports_filter_tenant_before_grouping_and_client_override(api):
    base, _ = api
    for tenant in TOKENS:
        result = get(base, "/api/reports?group_by=tenant&tenant=t2", TOKENS[tenant])
        assert result[0] == 200
        assert set(payload(result)["groups"]) == {tenant}
        assert payload(result)["groups"][tenant]["total_calls"] == 1
    assert payload(get(base, "/api/reports?tenant=t2", TOKENS["t1"]))["total_calls"] == 1
    assert payload(get(base, "/api/reports?operator=t2-recepcao", TOKENS["t1"]))["total_calls"] == 0


def test_scope_controls_exact_paths_preflight_and_cors(api):
    base, _ = api
    for path in ["/api/metrics/today", "/api/metrics/sla",
                 "/api/metrics/sla/history", "/api/reports"]:
        assert get(base, path, TOKENS["t1"], "https://attacker.invalid")[0] == 403
        good = get(base, path, TOKENS["t1"], "http://localhost:8082")
        assert good[0] == 200
        assert good[1]["Access-Control-Allow-Origin"] == "http://localhost:8082"
        assert good[1]["Vary"] == "Origin"
        assert good[1]["Cache-Control"] == "no-store"
        assert get(base, path, method="OPTIONS", origin="https://attacker.invalid")[0] == 403
        assert get(base, path, method="OPTIONS", origin="http://localhost:8082")[0] == 204
    for path in ["/api/metrics/today-extra", "/api/metrics/sla-evil",
                 "/api/metrics/sla/historyXX", "/api/reportsXYZ"]:
        assert get(base, path, TOKENS["t1"])[0] == 404


def test_revocation_affects_metric_routes_immediately(api):
    base, policy_file = api
    assert get(base, "/api/metrics/today", TOKENS["t1"])[0] == 200
    data = json.loads(policy_file.read_text())
    data["credentials"] = [entry for entry in data["credentials"]
                           if entry["tenant"] != "t1"]
    policy_file.write_text(json.dumps(data))
    assert get(base, "/api/metrics/today", TOKENS["t1"])[0] == 401
    assert get(base, "/api/metrics/sla/history", TOKENS["t1"])[0] == 401


@pytest.mark.parametrize("event", [
    {"Event": "Cdr", "Disposition": "ANSWERED"},
    {"Event": "Cdr", "AccountCode": "t01", "Disposition": "ANSWERED"},
    {"Event": "Cdr", "AccountCode": "t1evil", "Disposition": "ANSWERED"},
    {"Event": "Cdr", "AccountCode": "t1", "Accountcode": "t2", "Disposition": "ANSWERED"},
    {"Event": "Hangup", "AccountCode": "t1", "Disposition": "ANSWERED"},
    {"Event": "Cdr", "AccountCode": ["t1"], "Disposition": "ANSWERED"},
])
def test_ambiguous_or_missing_cdr_tenant_fails_closed(event):
    assert tenant_from_cdr(event) is None


def test_daily_metrics_reset_independently_after_midnight():
    instant = [1_700_000_000]
    metrics = TenantDailyMetrics(clock=lambda: instant[0])
    metrics.apply_cdr_event({"Event": "Cdr", "AccountCode": "t1",
                             "Disposition": "ANSWERED", "BillableSeconds": "30"})
    assert metrics.snapshot("t1")["total_calls"] == 1
    instant[0] += 90000
    assert metrics.snapshot("t1")["total_calls"] == 0
    assert metrics.snapshot("t2")["total_calls"] == 0
