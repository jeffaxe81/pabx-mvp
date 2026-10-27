"""HTTP real para operações de operador com tenant/papel; AMI é simulado."""
import hashlib
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest
import server
from agent_pause import PauseHistoryStore, validate_pause_request
from extension_states import ExtensionStateTracker
from presence import load_presence, set_presence, validate_presence_input

TOKENS = {"agent": "A" * 48, "supervisor": "S" * 48, "t2": "R" * 48}


@pytest.fixture
def api(tmp_path, monkeypatch):
    access = tmp_path / "queue-access.json"
    users = [
        {"token_sha256": hashlib.sha256(token.encode()).hexdigest(),
         "tenant": tenant, "role": role, "expires_at": 4102444800,
         **({"extension": ext} if ext else {})}
        for token, tenant, role, ext in [
            (TOKENS["agent"], "t1", "agent", "t1-recepcao"),
            (TOKENS["supervisor"], "t1", "supervisor", None),
            (TOKENS["t2"], "t2", "supervisor", None),
        ]
    ]
    access.write_text(json.dumps({"credentials": users}))
    access.chmod(0o600)
    presence_file = tmp_path / "presence.json"
    set_presence(presence_file, "t1-recepcao", "reuniao", "t1 private")
    set_presence(presence_file, "t2-recepcao", "ferias", "t2 private")
    history = PauseHistoryStore(tmp_path / "pause_history.jsonl")
    history.append({"extension": "t1-recepcao", "reason": "t1 private",
                    "started_at": 100, "duration_seconds": 13})
    history.append({"extension": "t2-recepcao", "reason": "t2 private",
                    "started_at": 100, "duration_seconds": 37})

    state = ExtensionStateTracker()
    for exten, context in [
        ("1010", "t1-hints"), ("1010", "t2-hints"), ("t1-recepcao", "t1-hints"),
        ("1010", "t10-hints"), ("1010", ""),
    ]:
        state.apply_event({"Event": "ExtensionStatus", "Exten": exten,
                           "Context": context, "Status": "0"})

    class AMISpy:
        def __init__(self):
            self.calls = []
        def pause_member(self, interface, paused, reason):
            self.calls.append((interface, paused, reason))
            return {"Response": "Success"}
    spy = AMISpy()
    monkeypatch.setattr(server, "QUEUE_ACCESS_POLICY_PATH", str(access))
    monkeypatch.setattr(server, "QUEUE_CORS_ORIGINS", {"http://localhost:8082"})
    monkeypatch.setattr(server, "PRESENCE_PATH", str(presence_file))
    monkeypatch.setattr(server, "pause_history_store", history)
    monkeypatch.setattr(server, "extension_states", state)
    monkeypatch.setattr(server, "ami", spy)

    http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:%s" % http.server_address[1], presence_file, spy
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=3)


def request(base, path, token=None, method="GET", payload=None, origin=None):
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    if origin is not None:
        headers["Origin"] = origin
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=4) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), err.read()


def test_all_operator_endpoints_deny_anonymous_without_mutation(api):
    base, presence, spy = api
    original = presence.read_bytes()
    for path in ["/api/presence", "/api/extension-states", "/api/reports/pauses"]:
        response = request(base, path)
        assert response[0] == 401
        assert "Access-Control-Allow-Origin" not in response[1]
        assert response[1]["Cache-Control"] == "no-store"
    for method, path, payload in [
        ("POST", "/api/presence/t1-recepcao", {"status": "ausente"}),
        ("DELETE", "/api/presence/t1-recepcao", None),
        ("POST", "/api/queue/pause", {"extension": "t1-recepcao",
                                       "paused": True, "reason": "almoço"}),
    ]:
        assert request(base, path, method=method, payload=payload)[0] == 401
    assert presence.read_bytes() == original and spy.calls == []


def test_agent_isolated_presence_and_pause_reports(api):
    base, _, _ = api
    presence = request(base, "/api/presence?tenant=t2", TOKENS["agent"])
    assert presence[0] == 200
    assert set(json.loads(presence[2])["presence"]) == {"t1-recepcao"}
    assert "t2 private".encode() not in presence[2]
    states = request(base, "/api/extension-states", TOKENS["agent"])
    assert states[0] == 200
    assert {s["context"] for s in json.loads(states[2])["extensions"]} == {"t1-hints"}
    assert len(json.loads(states[2])["extensions"]) == 2
    reports = request(base, "/api/reports/pauses", TOKENS["agent"])
    assert reports[0] == 200
    data = json.loads(reports[2])
    assert data["total_records"] == 1
    assert data["by_extension"]["t1-recepcao"]["total_seconds"] == 13
    assert b"t2 private" not in reports[2]


def test_t2_cannot_view_t1_data_even_using_tenant_query(api):
    base, _, _ = api
    result = request(base, "/api/presence?tenant=t1", TOKENS["t2"])
    assert set(json.loads(result[2])["presence"]) == {"t2-recepcao"}
    result = request(base, "/api/reports/pauses?tenant=t1", TOKENS["t2"])
    assert json.loads(result[2])["total_records"] == 1
    assert b"t1 private" not in result[2]


def test_operator_role_self_service_and_supervisor_scope(api):
    base, presence, spy = api
    # Agent cannot change colleague in same tenant nor another tenant.
    for extension in ["t1-recepcao-2", "t2-recepcao"]:
        assert request(base, "/api/presence/" + extension, TOKENS["agent"],
                       method="POST", payload={"status": "ausente"})[0] == 403
        assert request(base, "/api/presence/" + extension, TOKENS["agent"],
                       method="DELETE")[0] == 403
        assert request(base, "/api/queue/pause", TOKENS["agent"], method="POST",
                       payload={"extension": extension, "paused": True,
                                "reason": "almoço"})[0] == 403
    assert spy.calls == []
    assert load_presence(presence)["t2-recepcao"]["status"] == "ferias"

    response = request(base, "/api/presence/t1-recepcao", TOKENS["agent"],
                       method="POST", payload={"status": "ausente"})
    assert response[0] == 200
    assert load_presence(presence)["t1-recepcao"]["status"] == "ausente"
    assert request(base, "/api/queue/pause", TOKENS["agent"], method="POST",
                   payload={"extension": "t1-recepcao", "paused": True,
                            "reason": "pausa"})[0] == 200
    assert spy.calls == [("PJSIP/t1-recepcao", True, "pausa")]
    assert request(base, "/api/presence/t1-recepcao", TOKENS["agent"], method="DELETE")[0] == 200
    assert "t1-recepcao" not in load_presence(presence)

    assert request(base, "/api/presence/t1-recepcao-2", TOKENS["supervisor"],
                   method="POST", payload={"status": "reuniao"})[0] == 200
    assert request(base, "/api/presence/t2-recepcao", TOKENS["supervisor"],
                   method="POST", payload={"status": "ausente"})[0] == 403


def test_origin_and_preflight_reject_unapproved_browser(api):
    base, presence, spy = api
    before = presence.read_bytes()
    assert request(base, "/api/presence/t1-recepcao", TOKENS["agent"],
                   method="POST", payload={"status": "ausente"},
                   origin="https://attacker.invalid")[0] == 403
    assert request(base, "/api/queue/pause", TOKENS["agent"],
                   method="POST", payload={"extension": "t1-recepcao", "paused": True,
                                          "reason": "x"}, origin="null")[0] == 403
    assert spy.calls == [] and before == presence.read_bytes()
    for path in ["/api/presence", "/api/queue/pause", "/api/extension-states",
                 "/api/reports/pauses", "/api/presence/t1-recepcao"]:
        assert request(base, path, method="OPTIONS",
                       origin="https://attacker.invalid")[0] == 403
        response = request(base, path, method="OPTIONS",
                           origin="http://localhost:8082")
        assert response[0] == 204
        assert response[1]["Access-Control-Allow-Origin"] == "http://localhost:8082"


@pytest.mark.parametrize("bad", [
    {"status": 42}, {"status": ["ausente"]}, {"status": "ausente", "note": []},
    {"status": "ausente", "note": "x" * 257}, [],
])
def test_bad_presence_payload_returns_400(api, bad):
    base, _, _ = api
    assert request(base, "/api/presence/t1-recepcao", TOKENS["agent"],
                   method="POST", payload=bad)[0] == 400


@pytest.mark.parametrize("bad", [
    {"extension": [], "paused": True, "reason": "x"},
    {"extension": "t1-recepcao", "paused": True, "reason": []},
    {"extension": "t1-recepcao", "paused": True, "reason": "x" * 257},
    [],
])
def test_bad_pause_payload_returns_400_and_no_ami(api, bad):
    base, _, spy = api
    assert request(base, "/api/queue/pause", TOKENS["agent"],
                   method="POST", payload=bad)[0] == 400
    assert spy.calls == []


def test_validators_reject_non_dict_values():
    assert validate_presence_input(None)[0] is False
    assert validate_pause_request([])[0] is False
