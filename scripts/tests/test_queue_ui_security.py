"""Contrato de proteção do DOM e token temporário das filas no Webphone."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "webphone"


def section(path, start, end):
    source = (WEB / path).read_text(encoding="utf-8")
    assert start in source and end in source
    return source.split(start, 1)[1].split(end, 1)[0]


def test_webphone_queue_does_not_render_external_caller_id_as_html():
    body = section("index.html", "function renderQueue(apiUrl, waiting) {",
                   "function pickupFromQueue(apiUrl, channel) {")
    assert "textContent" in body
    assert "createElement(" in body
    assert "replaceChildren(" in body
    assert "innerHTML" not in body
    assert "dataset.channel =" not in body


def test_operations_panel_does_not_render_external_caller_id_as_html():
    body = section("painel-operacional.html", "function renderQueue(waiting) {", "fetchAll();")
    assert "textContent" in body
    assert "createElement(" in body
    assert "replaceChildren(" in body
    assert "innerHTML" not in body


def test_queue_tokens_are_password_fields_and_only_sent_in_authorization_header():
    for page in ["index.html", "painel-operacional.html"]:
        src = (WEB / page).read_text(encoding="utf-8")
        assert 'id="queueToken" type="password"' in src
        assert "Authorization: `Bearer ${token}`" in src
        assert "localStorage.setItem('queueToken'" not in src
        assert "sessionStorage.setItem('queueToken'" not in src
        assert "?token=" not in src


def test_queue_ui_denies_remote_http_bearer_requests():
    for page in ["index.html", "painel-operacional.html"]:
        src = (WEB / page).read_text(encoding="utf-8")
        assert "parsed.protocol === 'https:'" in src or "url.protocol === 'https:'" in src
        assert "'localhost', '127.0.0.1'" in src
