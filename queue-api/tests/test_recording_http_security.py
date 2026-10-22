"""Testes HTTP reais (loopback) das rotas sensíveis de gravações.

Não usam Asterisk, rede pública, clientes ou gravações de produção.
"""
import hashlib
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest
import server


TOKEN_T1 = "Q" * 48


@pytest.fixture
def recording_server(tmp_path, monkeypatch):
    base = tmp_path / "recordings"
    base.mkdir()
    (base / "t1.wav").write_bytes(b"RIFF tenant one")
    (base / "t2.wav").write_bytes(b"RIFF tenant two")

    path = tmp_path / "access.json"
    policy = {
        "credentials": [
            {
                "token_sha256": hashlib.sha256(TOKEN_T1.encode()).hexdigest(),
                "tenant": "t1", "role": "supervisor", "expires_at": 4102444800,
            },
        ],
        "recordings": {
            "t1.wav": {"tenant": "t1"},
            "t2.wav": {"tenant": "t2"},
        },
    }
    path.write_text(json.dumps(policy), encoding="utf-8")
    monkeypatch.setattr(server, "RECORDINGS_DIR", str(base))
    monkeypatch.setattr(server, "RECORDINGS_ACCESS_POLICY_PATH", str(path))
    monkeypatch.setattr(server, "RECORDINGS_CORS_ORIGINS", {"http://localhost:8082"})
    http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:{}".format(http.server_address[1]), path
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=2)


def request(url, *, auth=None, origin=None, method="GET"):
    headers = {}
    if auth:
        headers["Authorization"] = "Bearer " + auth
    if origin:
        headers["Origin"] = origin
    req = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def test_list_denies_anonymous_and_wrong_token(recording_server):
    url, _ = recording_server
    assert request(url + "/api/recordings")[0] == 401
    assert request(url + "/api/recordings", auth="z"*48)[0] == 401


def test_list_only_shows_same_tenant(recording_server):
    url, _ = recording_server
    status, headers, body = request(url + "/api/recordings", auth=TOKEN_T1)
    assert status == 200
    assert headers["Cache-Control"] == "no-store"
    assert [r["filename"] for r in json.loads(body)["recordings"]] == ["t1.wav"]


def test_file_does_not_reveal_cross_tenant_existence(recording_server):
    url, _ = recording_server
    assert request(url + "/recordings/t2.wav", auth=TOKEN_T1)[0] == 404
    status, _, payload = request(url + "/recordings/t1.wav", auth=TOKEN_T1)
    assert status == 200
    assert payload == b"RIFF tenant one"


def test_cors_allows_only_explicitly_configured_origin(recording_server):
    url, _ = recording_server
    status, headers, _ = request(url + "/api/recordings", auth=TOKEN_T1, origin="http://localhost:8082")
    assert status == 200
    assert headers["Access-Control-Allow-Origin"] == "http://localhost:8082"
    status, headers, _ = request(url + "/api/recordings", auth=TOKEN_T1, origin="http://attacker.test")
    assert status == 403
    assert "Access-Control-Allow-Origin" not in headers


def test_preflight_denies_unknown_origin(recording_server):
    url, _ = recording_server
    assert request(url + "/api/recordings", origin="https://attacker.test", method="OPTIONS")[0] == 403
    status, headers, _ = request(url + "/api/recordings", origin="http://localhost:8082", method="OPTIONS")
    assert status == 204
    assert headers["Access-Control-Allow-Headers"] == "Authorization"


def test_revocation_and_invalid_policy_take_effect_without_restart(recording_server):
    url, path = recording_server
    assert request(url + "/api/recordings", auth=TOKEN_T1)[0] == 200
    path.write_text("{}")
    assert request(url + "/api/recordings", auth=TOKEN_T1)[0] == 401
