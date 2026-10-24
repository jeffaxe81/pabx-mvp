"""Requisições HTTP reais para as filas; AMI simulado, sem Asterisk de produção."""
import hashlib
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import queue_access
import server
from queue_state import QueueStateTracker


TOKENS = {"agent": "A"*48, "supervisor": "S"*48, "t2": "R"*48, "t10": "T"*48}


def credential(token, tenant, role="supervisor", extension=None, expiry=4102444800):
    entry = {
        "token_sha256": hashlib.sha256(token.encode("ascii")).hexdigest(),
        "tenant": tenant, "role": role, "expires_at": expiry,
    }
    if extension is not None:
        entry["extension"] = extension
    return entry


def put_policy(path):
    path.write_text(json.dumps({"credentials": [
        credential(TOKENS["agent"], "t1", "agent", "t1-recepcao"),
        credential(TOKENS["supervisor"], "t1"),
        credential(TOKENS["t2"], "t2"),
        credential(TOKENS["t10"], "t10", "agent", "t10-recepcao"),
    ]}), encoding="utf-8")


@pytest.fixture
def api(tmp_path, monkeypatch):
    policy = tmp_path / "queue_access.json"
    put_policy(policy)
    tracker = QueueStateTracker()
    for channel, queue in [
        ("A", "fila-t1"), ("A-en", "fila-t1-en"),
        ("B", "fila-t2"), ("T", "fila-t10"), ("Bad", "fila-t1-unknown"),
    ]:
        tracker.apply_event({"Event": "QueueCallerJoin", "Queue": queue, "Channel": channel,
                             "CallerIDNum": channel + "-secret"})

    class AMI:
        def __init__(self):
            self.calls = []
        def redirect_channel(self, channel, context, exten):
            self.calls.append((channel, exten))
            return {"Response": "Success"}

    ami = AMI()
    monkeypatch.setattr(server, "state", tracker)
    monkeypatch.setattr(server, "ami", ami)
    monkeypatch.setattr(server, "QUEUE_ACCESS_POLICY_PATH", str(policy))
    monkeypatch.setattr(server, "QUEUE_CORS_ORIGINS", {"http://localhost:8082"})
    monkeypatch.setattr(server, "PICKUP_ALLOWED_EXTENSIONS",
                        ["t1-recepcao", "t1-recepcao-2", "t2-recepcao", "t10-recepcao"])
    http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:{}".format(http.server_address[1]), policy, ami
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=3)


def request(base, path="/api/queue", token=None, origin=None, method="GET", payload=None):
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    if origin is not None:
        headers["Origin"] = origin
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    else:
        data = None
    req = urllib.request.Request(base + path, headers=headers, method=method, data=data)
    try:
        with urllib.request.urlopen(req, timeout=4) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()


def channels(result):
    return {entry["channel"] for entry in json.loads(result[2])["waiting"]}


def test_no_key_never_leaks_queue_or_wildcard_cors(api):
    base, _, ami = api
    result = request(base)
    assert result[0] == 401
    assert result[1]["WWW-Authenticate"] == "Bearer"
    assert result[1]["Cache-Control"] == "no-store"
    assert "Access-Control-Allow-Origin" not in result[1]
    assert b"A-secret" not in result[2]
    result = request(base, "/api/queue/pickup", method="POST",
                     payload={"channel": "A", "extension": "t1-recepcao"})
    assert result[0] == 401 and ami.calls == []


def test_tenant_lists_are_separate_for_admin_agent_and_t10(api):
    base, _, _ = api
    assert channels(request(base, token=TOKENS["agent"])) == {"A", "A-en"}
    assert channels(request(base, token=TOKENS["supervisor"])) == {"A", "A-en"}
    assert channels(request(base, token=TOKENS["t2"])) == {"B"}
    assert channels(request(base, token=TOKENS["t10"])) == {"T"}
    assert channels(request(base, "/api/queue?tenant=t2", token=TOKENS["agent"])) == {"A", "A-en"}


def test_only_exact_queue_route_is_listed(api):
    base, _, _ = api
    assert request(base, "/api/queueXYZ", token=TOKENS["agent"])[0] == 404
    assert request(base, "/api/queue/pickup", token=TOKENS["agent"])[0] == 404


def test_origin_whitelist_and_preflight_are_independent_of_old_wildcard(api):
    base, _, _ = api
    bad = request(base, token=TOKENS["agent"], origin="https://attacker.invalid")
    assert bad[0] == 403 and "Access-Control-Allow-Origin" not in bad[1]
    assert request(base, token=TOKENS["agent"], origin="null")[0] == 403
    good = request(base, token=TOKENS["agent"], origin="http://localhost:8082")
    assert good[0] == 200
    assert good[1]["Access-Control-Allow-Origin"] == "http://localhost:8082"
    assert good[1]["Vary"] == "Origin"
    for path in ["/api/queue", "/api/queue/pickup"]:
        blocked = request(base, path, method="OPTIONS", origin="https://attacker.invalid")
        assert blocked[0] == 403
        allowed = request(base, path, method="OPTIONS", origin="http://localhost:8082")
        assert allowed[0] == 204
        assert allowed[1]["Access-Control-Allow-Headers"] == "Authorization, Content-Type"


def test_agent_cannot_redirect_colleague_with_same_tenant(api):
    base, _, ami = api
    claim = {"channel": "A", "extension": "t1-recepcao-2"}
    assert request(base, "/api/queue/pickup", token=TOKENS["agent"], method="POST", payload=claim)[0] == 403
    assert ami.calls == []
    ok = request(base, "/api/queue/pickup", token=TOKENS["supervisor"], method="POST", payload=claim)
    assert ok[0] == 200 and ami.calls == [("A", "t1-recepcao-2")]


def test_valid_agent_pickup_and_cross_tenant_spoofing(api):
    base, _, ami = api
    bad = {"channel": "B", "extension": "t1-recepcao", "queue": "fila-t1"}
    assert request(base, "/api/queue/pickup", token=TOKENS["agent"], method="POST", payload=bad)[0] == 403
    assert request(base, "/api/queue/pickup", token=TOKENS["t2"], method="POST",
                   payload={"channel": "A", "extension": "t1-recepcao"})[0] == 403
    assert ami.calls == []
    good = request(base, "/api/queue/pickup", token=TOKENS["agent"], method="POST",
                   payload={"channel": "A-en", "extension": "t1-recepcao"})
    assert good[0] == 200 and ami.calls == [("A-en", "t1-recepcao")]


def test_policy_revocation_invalid_schema_and_symlink_fail_closed(api, tmp_path):
    base, policy, ami = api
    assert request(base, token=TOKENS["agent"])[0] == 200
    put_policy(policy)
    data = json.loads(policy.read_text())
    data["credentials"] = data["credentials"][1:]
    policy.write_text(json.dumps(data))
    assert request(base, token=TOKENS["agent"])[0] == 401
    policy.write_text('{"credentials": [], "recordings": {}}')
    assert request(base, token=TOKENS["supervisor"])[0] == 401
    policy.unlink()
    outside = tmp_path / "outside.json"
    put_policy(outside)
    policy.symlink_to(outside)
    assert request(base, token=TOKENS["agent"])[0] == 401
    assert ami.calls == []


@pytest.mark.parametrize("invalid", [
    {"credentials": [credential("X"*48, "t1", "agent", "t2-recepcao")]},
    {"credentials": [credential("X"*48, "t1", "supervisor", "t1-recepcao")]},
    {"credentials": [credential("X"*48, "t01")]},
    {"credentials": [credential("X"*48, "t1", expiry=float("inf"))]},
    {"credentials": [credential("X"*48, "t1"), credential("X"*48, "t1")]},
    {"credentials": [], "recordings": {}},
    {"credentials": "not-a-list"},
])
def test_invalid_credential_schema_rejected(tmp_path, invalid):
    policy = tmp_path / "access.json"
    policy.write_text(json.dumps(invalid))
    assert queue_access.load_queue_policy(policy) is None


def test_queue_policy_expiration_and_agent_role_restriction(tmp_path):
    policy = tmp_path / "access.json"
    item = credential("X"*48, "t1", "agent", "t1-recepcao", expiry=1000)
    policy.write_text(json.dumps({"credentials": [item]}))
    loaded = queue_access.load_queue_policy(policy)
    assert queue_access.authenticate_queue("Bearer " + "X"*48, loaded, now=999) is not None
    assert queue_access.authenticate_queue("Bearer " + "X"*48, loaded, now=1000) is None
    assert queue_access.may_pickup(item, "t1-recepcao")
    assert not queue_access.may_pickup(item, "t1-recepcao-2")
    assert not queue_access.may_pickup(item, "t2-recepcao")
