"""HTTP integration: monitoring data must never be returned across tenants."""
import hashlib
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import server
from fraud_detection import FraudAlertsLog
from missed_calls import MissedCallsLog
from monitoring_access import (
    channel_tenant, extension_tenant, monitoring_event_tenant,
    scoped_monitoring_entries,
)
from quality_monitoring import QualityLog, parse_quality_event

TOKENS = {"t1": "A" * 48, "t2": "B" * 48, "t10": "C" * 48}


@pytest.fixture
def api(tmp_path, monkeypatch):
    policy = tmp_path / "queue_access.json"
    policy.write_text(json.dumps({"credentials": [{
        "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
        "tenant": tenant, "role": "supervisor", "expires_at": 4102444800,
    } for tenant, token in TOKENS.items()]}), encoding="utf-8")
    policy.chmod(0o600)
    missed, alerts, quality = MissedCallsLog(), FraudAlertsLog(), QualityLog()
    for tenant in TOKENS:
        missed.append({"tenant": tenant, "caller_id_name": "PRIVATE-" + tenant,
                       "caller_id_num": "55119999" + tenant,
                       "destination": "fila-" + tenant, "reason": "ABANDONED"})
        alerts.append("volume_anormal", tenant + "-recepcao",
                      "ALERT-PRIVATE-" + tenant)
        quality.append({"tenant": tenant,
                        "channel": "PJSIP/" + tenant + "-recepcao-00000001",
                        "jitter_ms": 80.0, "packet_loss_percent": 2}, poor=True)
    missed.append({"caller_id_name": "UNKNOWN", "reason": "ABANDONED"})
    missed.append({"tenant": None, "caller_id_name": "UNATTRIBUTED", "reason": "ABANDONED"})
    alerts.append("volume_anormal", "unknown-extension", "UNATTRIBUTED")
    quality.append({"channel": "PJSIP/unknown-00000000"}, poor=True)

    monkeypatch.setattr(server, "missed_calls_log", missed)
    monkeypatch.setattr(server, "fraud_alerts_log", alerts)
    monkeypatch.setattr(server, "quality_log", quality)
    monkeypatch.setattr(server, "QUEUE_ACCESS_POLICY_PATH", str(policy))
    monkeypatch.setattr(server, "QUEUE_CORS_ORIGINS", {"http://localhost:8082"})
    http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:{}".format(http.server_address[1]), policy
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=3)


def req(base, path, token=None, origin=None, method="GET"):
    headers = {}
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    if origin is not None:
        headers["Origin"] = origin
    request = urllib.request.Request(base + path, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()


@pytest.mark.parametrize("path", [
    "/api/missed-calls", "/api/fraud-alerts", "/api/quality",
    "/api/quality?only_poor=true",
])
def test_anonymous_is_denied_with_no_caller_data(api, path):
    base, _ = api
    response = req(base, path)
    assert response[0] == 401
    assert response[1]["Cache-Control"] == "no-store"
    assert response[1]["WWW-Authenticate"] == "Bearer"
    assert b"PRIVATE-" not in response[2]
    assert "Access-Control-Allow-Origin" not in response[1]


@pytest.mark.parametrize("path,key", [
    ("/api/missed-calls", "missed_calls"),
    ("/api/fraud-alerts", "alerts"),
    ("/api/quality?only_poor=true", "quality_reports"),
])
def test_authenticated_tenant_only_sees_own_entries(api, path, key):
    base, _ = api
    for tenant, token in TOKENS.items():
        status, headers, raw = req(base, path + ("&tenant=t2" if "?" in path else "?tenant=t2"), token)
        assert status == 200
        entries = json.loads(raw)[key]
        assert len(entries) == 1
        assert {entry["tenant"] for entry in entries} == {tenant}
        assert b"UNATTRIBUTED" not in raw
        for other in TOKENS:
            if other != tenant:
                # Compara o valor completo: PRIVATE-t1 é prefixo de
                # PRIVATE-t10 e não indica vazamento entre empresas.
                assert ("PRIVATE-" + other + '"').encode() not in raw


@pytest.mark.parametrize("path", [
    "/api/missed-calls", "/api/fraud-alerts", "/api/quality",
])
def test_cors_preflight_and_exact_route(api, path):
    base, _ = api
    blocked = req(base, path, TOKENS["t1"], "https://untrusted.invalid")
    assert blocked[0] == 403 and "Access-Control-Allow-Origin" not in blocked[1]
    good = req(base, path, TOKENS["t1"], "http://localhost:8082")
    assert good[0] == 200
    assert good[1]["Access-Control-Allow-Origin"] == "http://localhost:8082"
    assert good[1]["Vary"] == "Origin"
    assert req(base, path, method="OPTIONS", origin="https://untrusted.invalid")[0] == 403
    assert req(base, path, method="OPTIONS", origin="http://localhost:8082")[0] == 204
    assert req(base, path + "-evil", TOKENS["t1"])[0] == 404


def test_revocation_and_bad_catalog_fail_closed(api):
    base, policy = api
    assert req(base, "/api/missed-calls", TOKENS["t1"])[0] == 200
    policy.write_text('{"credentials":[]}')
    assert req(base, "/api/missed-calls", TOKENS["t1"])[0] == 401
    assert req(base, "/api/quality", TOKENS["t1"])[0] == 401


@pytest.mark.parametrize("extension,tenant", [
    ("t1-recepcao", "t1"), ("t10-recepcao", "t10"),
    ("t01-recepcao", None), ("t1", None), ("xt1-recepcao", None),
    ("t1-recepcao/t2", None), ("t1-recepcao-2", "t1"),
])
def test_extension_tenant_parser_is_exact(extension, tenant):
    assert extension_tenant(extension) == tenant


@pytest.mark.parametrize("channel,tenant", [
    ("PJSIP/t1-recepcao-00000001", "t1"),
    ("PJSIP/t10-recepcao-00000001", "t10"),
    ("PJSIP/t1-recepcao/t2-00000001", None),
    ("PJSIP/t1-recepcao-bad", None),
    ("PJSIP/t01-recepcao-00000001", None),
    ("SIP/t1-recepcao-00000001", None),
])
def test_channel_tenant_parser_is_exact(channel, tenant):
    assert channel_tenant(channel) == tenant


def test_ami_missed_queue_and_quality_derive_only_unambiguous_tenant():
    assert monitoring_event_tenant({
        "Event": "QueueCallerAbandon", "Queue": "fila-t1-en"}) == "t1"
    assert monitoring_event_tenant({
        "Event": "QueueCallerAbandon", "Queue": "fila-t10"}) == "t10"
    assert monitoring_event_tenant({
        "Event": "QueueCallerAbandon", "Queue": "fila-t1evil"}) is None
    assert monitoring_event_tenant({
        "Event": "DialEnd", "Channel": "PJSIP/t1-recepcao-00000001"}) == "t1"
    assert monitoring_event_tenant({
        "Event": "DialEnd", "Channel": "PJSIP/t1-recepcao-00000001",
        "AccountCode": "t2"}) is None
    assert monitoring_event_tenant({
        "Event": "UserEvent", "UserEvent": "QualityStats",
        "Channel": "PJSIP/t1-recepcao-00000001"}) == "t1"
    assert monitoring_event_tenant({
        "Event": "UserEvent", "UserEvent": "QualityStats",
        "Channel": "PJSIP/unknown-00000001"}) is None
    assert monitoring_event_tenant({
        "Event": "DialEnd", "DialStatus": "BUSY"}) is None


def test_scoped_results_drop_legacy_unattributed_data():
    assert scoped_monitoring_entries([
        {"tenant": "t1", "value": "visible"},
        {"tenant": None, "value": "no"}, {"value": "no"},
        {"tenant": "t10", "value": "no"},
    ], "t1") == [{"tenant": "t1", "value": "visible"}]


def test_handle_ami_event_records_queue_abandon_with_verified_tenant(monkeypatch):
    log = MissedCallsLog()
    notified = []
    monkeypatch.setattr(server, "missed_calls_log", log)
    monkeypatch.setattr(server, "NOTIFY_TENANT", "t1")
    monkeypatch.setattr(server, "dispatch_notifications",
                        lambda missed, config: notified.append(missed) or [])
    monkeypatch.setattr(server, "dispatch_screen_pop", lambda *args: None)
    event = {"Event": "QueueCallerAbandon", "Queue": "fila-t1",
             "CallerIDNum": "5511999000000"}
    server.handle_ami_event(event)
    assert len(log.list()) == 1
    assert log.list()[0]["tenant"] == "t1"
    assert len(notified) == 1
    server.handle_ami_event({"Event": "QueueCallerAbandon",
                             "Queue": "fila-t1evil", "CallerIDNum": "UNSAFE"})
    assert len(log.list()) == 1
    assert len(notified) == 1


def test_quality_instrumentation_has_tenant_from_channel(monkeypatch):
    log = QualityLog()
    monkeypatch.setattr(server, "quality_log", log)
    monkeypatch.setattr(server, "dispatch_screen_pop", lambda *args: None)
    event = {"Event": "UserEvent", "UserEvent": "QualityStats",
             "Channel": "PJSIP/t2-recepcao-00000001",
             "Jitter": "55", "PacketLoss": "5"}
    server.handle_ami_event(event)
    assert len(log.list()) == 1
    assert log.list()[0]["tenant"] == "t2"
    assert log.list()[0]["poor"] is True


def test_legacy_global_notification_targets_deny_other_tenants(monkeypatch):
    log = MissedCallsLog()
    outgoing = []
    monkeypatch.setattr(server, "missed_calls_log", log)
    monkeypatch.setattr(server, "NOTIFY_TENANT", "t1")
    monkeypatch.setattr(server, "dispatch_notifications",
                        lambda missed, config: outgoing.append(missed) or [])
    monkeypatch.setattr(server, "dispatch_screen_pop", lambda *args: None)
    server.handle_ami_event({"Event": "QueueCallerAbandon",
                             "Queue": "fila-t2", "CallerIDNum": "PRIVATE-t2"})
    assert len(log.list()) == 1
    assert log.list()[0]["tenant"] == "t2"
    assert outgoing == []

    monkeypatch.setattr(server, "NOTIFY_TENANT", "")
    server.handle_ami_event({"Event": "QueueCallerAbandon",
                             "Queue": "fila-t1", "CallerIDNum": "PRIVATE-t1"})
    assert len(log.list()) == 2
    assert outgoing == []


def test_monitoring_tenant_parser_rejects_oversized_identifiers():
    from monitoring_access import extension_tenant, channel_tenant
    for invalid in (None, [], "t1-" + "a" * 100000):
        assert extension_tenant(invalid) is None
    assert channel_tenant("PJSIP/t1-" + "x" * 100000 + "-00000001") is None


def test_supervision_summary_20_metrics_isolation_and_no_pii(api, monkeypatch):
    """O resumo não pode devolver CallerID ou linhas de outro tenant."""
    base, _ = api
    monkeypatch.setattr(server.state, "waiting_list", lambda: [
        {"queue": "fila-t1-en", "waiting_seconds": 67,
         "caller_id_num": "PRIVATE-CALLER-T1", "channel": "SECRET-T1"},
        {"queue": "fila-t10", "waiting_seconds": 99,
         "caller_id_num": "PRIVATE-CALLER-T10", "channel": "SECRET-T10"},
    ])
    monkeypatch.setattr(server.extension_states, "snapshot", lambda: [
        {"context": "t1-hints", "exten": "t1-recepcao", "status_label": "livre"},
        {"context": "t10-hints", "exten": "t10-recepcao", "status_label": "ocupado"},
    ])
    monkeypatch.setattr(server.queue_sla_tracker, "snapshot", lambda: {
        "fila-t1-en": {"offered": 10, "within_sla": 8},
        "fila-t10": {"offered": 100, "within_sla": 0},
    })
    monkeypatch.setattr(server.agent_pause_store, "snapshot", lambda: {
        "t1-recepcao": {"paused": True},
        "t10-recepcao": {"paused": True},
    })
    monkeypatch.setattr(server, "load_presence", lambda path: {
        "t1-recepcao": {"status": "ausente", "note": "PRIVATE-NOTE"},
        "t10-recepcao": {"status": "ausente"},
    })
    status, headers, raw = req(base, "/api/supervision/summary?tenant=t10",
                               TOKENS["t1"], "http://localhost:8082")
    assert status == 200
    assert headers["Cache-Control"] == "no-store"
    assert headers["Access-Control-Allow-Origin"] == "http://localhost:8082"
    result = json.loads(raw)
    assert result["tenant"] == "t1"
    assert result["metric_count"] == 20
    diagnostics = result["diagnostics"]
    assert diagnostics["tenant"] == "t1"
    assert diagnostics["rule_count"] == 20
    assert len(diagnostics["rules"]) == 20
    assert diagnostics["evaluation"] == "reference_only_not_automatic_remediation"
    assert diagnostics["operational_homologation_claimed"] is False
    assert all(rule["reference_is_contractual"] is False
               for rule in diagnostics["rules"])
    assert sum(len(result[section]) for section in
               ("queues", "extensions", "sla", "observations")) == 20
    assert result["queues"]["waiting_calls"] == 1
    assert result["queues"]["waiting_over_60_seconds"] == 1
    assert result["extensions"]["free_extensions"] == 1
    assert result["extensions"]["busy_extensions"] == 0
    assert result["sla"]["offered_calls"] == 10
    assert result["sla"]["weighted_sla_percent"] == 80
    assert result["observations"]["paused_agents_snapshot"] == 1
    assert result["observations"]["manual_absent_overrides"] == 1
    assert result["observations"]["missed_events_in_buffer"] == 1
    assert result["observations"]["fraud_alerts_in_buffer"] == 1
    assert result["observations"]["poor_quality_samples_in_buffer"] == 1
    for private in (b"PRIVATE-", b"SECRET-", b"note", b"channel", b"caller_id"):
        assert private not in raw

    status, _, raw = req(base, "/api/supervision/summary?tenant=t1", TOKENS["t10"])
    assert status == 200
    other = json.loads(raw)
    assert other["tenant"] == "t10"
    assert other["queues"]["waiting_calls"] == 1
    assert other["sla"]["offered_calls"] == 100
    assert other["extensions"]["busy_extensions"] == 1


def test_supervision_summary_restricts_agent_origin_and_revocation(api):
    base, policy = api
    path = "/api/supervision/summary"
    assert req(base, path)[0] == 401
    assert req(base, path, TOKENS["t1"], "https://attacker.invalid")[0] == 403
    assert req(base, path, method="OPTIONS", origin="https://attacker.invalid")[0] == 403
    assert req(base, path, method="OPTIONS", origin="http://localhost:8082")[0] == 204
    assert req(base, path + "-evil", TOKENS["t1"])[0] == 404

    token = "D" * 48
    catalog = json.loads(policy.read_text(encoding="utf-8"))
    catalog["credentials"].append({
        "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
        "tenant": "t1", "role": "agent",
        "extension": "t1-recepcao", "expires_at": 4102444800,
    })
    policy.write_text(json.dumps(catalog), encoding="utf-8")
    policy.chmod(0o600)
    status, _, raw = req(base, path, token)
    assert status == 403 and b"PRIVATE-" not in raw

    policy.write_text('{"credentials":[]}', encoding="utf-8")
    assert req(base, path, TOKENS["t1"])[0] == 401
