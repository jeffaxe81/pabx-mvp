"""Monitoring outputs must neither leak Bearer nor inject AMI caller data into DOM."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "webphone"


def method(filename, begin, end):
    source = (WEB / filename).read_text(encoding="utf-8")
    assert begin in source and end in source
    return source.split(begin, 1)[1].split(end, 1)[0]


def test_missed_calls_dom_never_interpolates_external_caller_id():
    body = method("index.html", "function renderMissedCalls(missedCalls) {",
                  "// ---------- Métricas do dia ----------")
    assert "textContent" in body
    assert "createElement" in body
    assert "innerHTML" not in body


def test_quality_and_fraud_dom_are_text_only():
    body = method("painel-operacional.html", "function appendMonitorRow(",
                  "function renderMetrics(m) {")
    for function in ("function renderQuality(", "function renderFraudAlerts("):
        assert function in body
    assert "textContent" in body
    assert "createTextNode" in body
    assert "innerHTML" not in body


def test_monitor_endpoints_require_credential_and_https():
    index = (WEB / "index.html").read_text(encoding="utf-8")
    ops = (WEB / "painel-operacional.html").read_text(encoding="utf-8")
    section = method("index.html", "function fetchMissedCalls(", "function renderMissedCalls(")
    assert "Authorization:" in section and "Bearer" in section
    assert "recordingApiIsSecure(apiUrl)" in section
    assert "cache: 'no-store'" in section
    for resource in ("/api/fraud-alerts", "/api/quality?only_poor=true"):
        assert "fetchScopedOperator('" + resource + "', token)" in ops
    assert "generation !== requestGeneration" in ops
    assert "clearProtectedPanels(" in ops
    assert "localStorage.setItem('queueToken'" not in index
