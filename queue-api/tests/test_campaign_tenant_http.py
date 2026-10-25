"""HTTP real: campanhas/callbacks exigem Bearer+chave, registros separados.

Roda em loopback e usa um AMI falso; nenhuma chamada real é feita.
"""
import hashlib
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import server
from campaigns import load_campaigns, create_campaign, mark_contact_calling
from callbacks import add_callback_request, load_callbacks, mark_callback_calling
from survey import SurveyStore

TOKENS = {"t1": "A"*48, "t2": "B"*48, "agent": "C"*48}
KEY = "secondary-key-only-for-tests"


@pytest.fixture
def api(tmp_path, monkeypatch):
    policy = tmp_path / "credentials.json"
    entries = []
    for token, tenant, role, ext in [
        (TOKENS["t1"], "t1", "supervisor", None),
        (TOKENS["t2"], "t2", "supervisor", None),
        (TOKENS["agent"], "t1", "agent", "t1-recepcao"),
    ]:
        row = {"token_sha256": hashlib.sha256(token.encode()).hexdigest(),
               "tenant": tenant, "role": role, "expires_at": 4102444800}
        if ext:
            row["extension"] = ext
        entries.append(row)
    policy.write_text(json.dumps({"credentials": entries}))
    policy.chmod(0o600)

    campaigns = tmp_path / "campaigns.json"
    callbacks = tmp_path / "callbacks.json"
    survey = tmp_path / "surveys.jsonl"
    for tenant in ["t1", "t2"]:
        create_campaign(campaigns, {"name": "PRIVATE-" + tenant,
                                   "agent_extension": tenant + "-recepcao",
                                   "tenant": tenant,
                                   "contacts": ["11999998888"]})
        add_callback_request(callbacks, "11999998888", "CLIENT-" + tenant, tenant=tenant)
        SurveyStore(survey).append({"tenant": tenant, "operator": tenant + "-recepcao",
                                    "score": 5 if tenant == "t1" else 1,
                                    "date": "2026-10-25"})
    # Registros antigos sem tenant devem permanecer invisíveis.
    create_campaign(campaigns, {"name": "LEGACY", "agent_extension": "t1-recepcao",
                                "contacts": ["11999998888"]})
    add_callback_request(callbacks, "11999998888", "LEGACY")

    class AMI:
        def __init__(self):
            self.actions = []
        def send_action(self, action):
            self.actions.append(action)
            return {"Response": "Success"}
    ami = AMI()
    monkeypatch.setattr(server, "CAMPAIGNS_PATH", str(campaigns))
    monkeypatch.setattr(server, "CALLBACKS_PATH", str(callbacks))
    monkeypatch.setattr(server, "SURVEY_PATH", str(survey))
    monkeypatch.setattr(server, "QUEUE_ACCESS_POLICY_PATH", str(policy))
    monkeypatch.setattr(server, "QUEUE_CORS_ORIGINS", {"http://localhost:8082"})
    monkeypatch.setattr(server, "CLICK_TO_CALL_CONFIG",
                        {"api_key": KEY, "allowed_extensions": ["t1-recepcao", "t2-recepcao"]})
    monkeypatch.setattr(server, "ami", ami)
    http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:{}".format(http.server_address[1]), campaigns, callbacks, ami, policy
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=3)


def request(base, path, token=None, key=None, method="GET", payload=None, origin=None):
    headers = {}
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    if key is not None:
        headers["X-Click-To-Call-Key"] = key
    if origin is not None:
        headers["Origin"] = origin
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, method=method, headers=headers, data=data)
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            return res.status, dict(res.headers), json.loads(res.read() or b"{}")
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), json.loads(err.read() or b"{}")


def own(api, path, tenant="t1", method="GET", payload=None):
    return request(api[0], path, TOKENS[tenant], KEY, method, payload)


@pytest.mark.parametrize("path,method,payload", [
    ("/api/campaigns", "GET", None),
    ("/api/campaigns", "POST",
     {"name": "x", "agent_extension": "t1-recepcao", "contacts": ["11999998888"]}),
    ("/api/callbacks", "GET", None),
    ("/api/callbacks/dial-next", "POST", None),
])
def test_both_independent_secrets_required(api, path, method, payload):
    base, _, _, ami, _ = api
    assert request(base, path, key=KEY, method=method, payload=payload)[0] == 401
    assert request(base, path, TOKENS["t1"], method=method, payload=payload)[0] == 403
    assert request(base, path, TOKENS["agent"], KEY, method=method, payload=payload)[0] == 403
    assert ami.actions == []


def test_campaign_list_and_id_are_scoped_and_legacy_invisible(api):
    base, campaigns, _, _, _ = api
    for tenant in ["t1", "t2"]:
        result = own(api, "/api/campaigns?tenant=" + ("t2" if tenant == "t1" else "t1"), tenant)
        assert result[0] == 200
        assert len(result[2]["campaigns"]) == 1
        campaign = result[2]["campaigns"][0]
        assert campaign["tenant"] == tenant
        assert campaign["name"] == "PRIVATE-" + tenant
        foreign = next(c for c in load_campaigns(campaigns) if c.get("tenant") != tenant
                       and c.get("tenant"))
        assert own(api, "/api/campaigns/" + foreign["id"], tenant)[0] == 404


def test_campaign_create_forces_tenant_and_blocks_other_extension(api):
    _, campaigns, _, ami, _ = api
    record = {"name": "spoof", "tenant": "t2",
              "agent_extension": "t1-recepcao", "contacts": ["11999998888"]}
    created = own(api, "/api/campaigns", method="POST", payload=record)
    assert created[0] == 201
    assert created[2]["tenant"] == "t1"
    assert load_campaigns(campaigns)[-1]["tenant"] == "t1"
    record["agent_extension"] = "t2-recepcao"
    assert own(api, "/api/campaigns", method="POST", payload=record)[0] == 403
    assert ami.actions == []


def test_campaign_dial_next_rejects_foreign_id_before_ami(api):
    _, campaigns, _, ami, _ = api
    foreign = next(c for c in load_campaigns(campaigns) if c.get("tenant") == "t2")
    path = "/api/campaigns/" + foreign["id"] + "/dial-next"
    assert own(api, path, method="POST")[0] == 404
    assert ami.actions == []
    allowed = next(c for c in load_campaigns(campaigns) if c.get("tenant") == "t1")
    result = own(api, "/api/campaigns/" + allowed["id"] + "/dial-next", method="POST")
    assert result[0] == 200
    assert len(ami.actions) == 1
    assert ami.actions[0]["Account"] == "t1"


def test_callback_list_and_originate_never_mix_tenants(api):
    _, campaigns, callbacks, ami, _ = api
    results = own(api, "/api/callbacks")
    assert results[0] == 200
    assert len(results[2]["callbacks"]) == 1
    assert results[2]["callbacks"][0]["tenant"] == "t1"
    out = own(api, "/api/callbacks/dial-next", method="POST")
    assert out[0] == 200
    assert ami.actions[-1]["Variable"] == "TENANT=t1"
    assert ami.actions[-1]["Account"] == "t1"
    assert ami.actions[-1]["Context"] == server.CALLBACK_CONNECT_CONTEXT
    assert load_callbacks(callbacks)[0]["status"] == "discando"
    assert own(api, "/api/callbacks/dial-next", method="POST")[2]["done"] is True


def test_survey_query_is_bearer_only_and_tenant_scoped(api):
    base, _, _, _, _ = api
    assert request(base, "/api/satisfaction")[0] == 401
    assert request(base, "/api/satisfaction", key=KEY)[0] == 401
    for tenant, expected in [("t1", 5), ("t2", 1)]:
        result = request(base, "/api/satisfaction?tenant=t1", TOKENS[tenant])
        assert result[0] == 200
        assert result[2]["count"] == 1
        assert result[2]["average"] == expected
        grouped = request(base, "/api/satisfaction?group_by=operator", TOKENS[tenant])
        assert list(grouped[2]["by_operator"]) == [tenant + "-recepcao"]


def test_secure_headers_origin_and_exact_routes(api):
    base, _, _, ami, _ = api
    for path in ["/api/campaigns", "/api/callbacks", "/api/satisfaction"]:
        blocked = request(base, path, TOKENS["t1"], KEY, origin="https://evil.invalid")
        assert blocked[0] == 403 and "Access-Control-Allow-Origin" not in blocked[1]
        good = request(base, path, TOKENS["t1"], KEY, origin="http://localhost:8082")
        assert good[0] == 200 and good[1]["Cache-Control"] == "no-store"
        assert good[1]["Access-Control-Allow-Origin"] == "http://localhost:8082"
        assert request(base, path, method="OPTIONS", origin="https://evil.invalid")[0] == 403
        assert request(base, path, method="OPTIONS", origin="http://localhost:8082")[0] == 204
    for bad_path in ["/api/campaigns-everything", "/api/callbacksXXX", "/api/satisfaction-extra"]:
        assert request(base, bad_path, TOKENS["t1"], KEY)[0] == 404
    assert ami.actions == []


def test_revoked_bearer_cannot_trigger_originate(api):
    base, _, callbacks, ami, policy = api
    data = json.loads(policy.read_text())
    data["credentials"] = [item for item in data["credentials"] if item["tenant"] != "t1"]
    policy.write_text(json.dumps(data))
    assert request(base, "/api/callbacks/dial-next", TOKENS["t1"], KEY, method="POST")[0] == 401
    assert ami.actions == []


def test_outbound_results_require_known_tenant_even_if_numbers_equal(api, monkeypatch):
    _, campaigns, callbacks, _, _ = api
    t1 = next(c for c in load_campaigns(campaigns) if c.get("tenant") == "t1")
    t2 = next(c for c in load_campaigns(campaigns) if c.get("tenant") == "t2")
    number = t1["contacts"][0]["number"]
    mark_contact_calling(campaigns, t1["id"], number)
    mark_contact_calling(campaigns, t2["id"], number)
    t1callback = next(c for c in load_callbacks(callbacks) if c.get("tenant") == "t1")
    t2callback = next(c for c in load_callbacks(callbacks) if c.get("tenant") == "t2")
    mark_callback_calling(callbacks, t1callback["id"])
    mark_callback_calling(callbacks, t2callback["id"])
    event = {"Event": "DialEnd", "DialStatus": "ANSWER",
             "Dialstring": "PJSIP/" + number + "@gateway-tdm"}
    server.apply_campaign_dial_result(event)
    server.apply_callback_dial_result(event)
    assert next(c for c in load_campaigns(campaigns) if c["id"] == t1["id"])["contacts"][0]["status"] == "discando"
    event["AccountCode"] = "t2"
    server.apply_campaign_dial_result(event)
    server.apply_callback_dial_result(event)
    assert next(c for c in load_campaigns(campaigns) if c["id"] == t2["id"])["contacts"][0]["status"] == "atendida"
    assert next(c for c in load_campaigns(campaigns) if c["id"] == t1["id"])["contacts"][0]["status"] == "discando"
    assert next(c for c in load_callbacks(callbacks) if c["id"] == t2callback["id"])["status"] == "concluido"
    assert next(c for c in load_callbacks(callbacks) if c["id"] == t1callback["id"])["status"] == "discando"
    event["AccountCode"] = "t1"
    event["Channel"] = "PJSIP/t2-recepcao-00000001"
    assert server.outbound_event_tenant(event) is None
