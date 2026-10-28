"""Regressão HTTP: rotas sem classificação não podem habilitar CORS amplo.

Teste de superfície HTTP em loopback; não inicia Asterisk nem origina chamadas.
"""
import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import pytest

import server


@pytest.fixture
def http_api(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "QUEUE_CORS_ORIGINS", {"https://painel.example"})
    monkeypatch.setattr(server, "RECORDINGS_CORS_ORIGINS", {"https://gravacoes.example"})
    # Nenhum token deve ser aceito quando o catálogo ainda não foi criado.
    monkeypatch.setattr(server, "QUEUE_ACCESS_POLICY_PATH", str(tmp_path / "missing.json"))
    api = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=api.serve_forever, daemon=True)
    thread.start()
    try:
        yield api.server_address[1]
    finally:
        api.shutdown()
        api.server_close()
        thread.join(timeout=3)


def request(port, method, path, origin="https://site-nao-autorizado.example"):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=4)
    try:
        conn.request(method, path, headers={"Origin": origin})
        response = conn.getresponse()
        status, headers, body = response.status, dict(response.getheaders()), response.read()
        return status, headers, body
    finally:
        conn.close()


@pytest.mark.parametrize("method", ["GET", "POST", "DELETE", "OPTIONS"])
@pytest.mark.parametrize("path", ["/api/nao-existe", "/privado?tenant=t2"])
def test_unknown_route_fails_closed_without_cors(http_api, method, path):
    status, headers, body = request(http_api, method, path)
    assert status == 404
    assert "Access-Control-Allow-Origin" not in headers
    assert "Access-Control-Allow-Methods" not in headers
    assert "Access-Control-Allow-Headers" not in headers
    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert int(headers["Content-Length"]) == len(body)
    assert json.loads(body) == {"error": "not found"}


def test_known_queue_route_still_requires_identity(http_api):
    status, headers, body = request(http_api, "GET", "/api/queue", "https://painel.example")
    assert status == 401
    assert headers["Access-Control-Allow-Origin"] == "https://painel.example"
    assert headers["WWW-Authenticate"] == "Bearer"
    assert json.loads(body)["error"]


def test_known_queue_preflight_stays_restricted_and_has_empty_body(http_api):
    status, headers, body = request(http_api, "OPTIONS", "/api/queue", "https://painel.example")
    assert status == 204
    assert headers["Access-Control-Allow-Origin"] == "https://painel.example"
    assert int(headers["Content-Length"]) == 0
    assert body == b""

    status, headers, body = request(http_api, "OPTIONS", "/api/queue")
    assert status == 403
    assert "Access-Control-Allow-Origin" not in headers
    assert json.loads(body)["error"]
