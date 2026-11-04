"""Testa HTTP de controle de membros com AMI simulado em localhost."""
import hashlib
import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import pytest
import server
from queue_membership import QueueMemberTracker

ORIGIN = "https://axe.example.invalid"
TOKENS = {"agent":"A"*48,"supervisor":"S"*48,"t2":"T"*48}


class AMISpy:
    def __init__(self):
        self.actions = []
        self.response = {"Response":"Success"}

    def send_action(self, action):
        self.actions.append(dict(action))
        return dict(self.response)


def request(port, path, *, token=None, method="GET", data=None, origin=None,
            raw=None, headers=None):
    headers = dict(headers or {})
    if token:
        headers["Authorization"] = "Bearer " + token
    if origin:
        headers["Origin"] = origin
    if data is not None:
        headers["Content-Type"] = "application/json"
        raw = json.dumps(data).encode()
    client = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        client.request(method, path, body=raw, headers=headers)
        response = client.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        client.close()


@pytest.fixture
def service(tmp_path, monkeypatch):
    policy = tmp_path / "queue-policy.json"
    policy.write_text(json.dumps({"credentials":[
        {
            "token_sha256":hashlib.sha256(token.encode()).hexdigest(),
            "tenant":tenant, "role":role, "expires_at":4102444800,
            **({"extension":"t1-recepcao"} if role=="agent" else {}),
        }
        for token,tenant,role in [
            (TOKENS["agent"],"t1","agent"),
            (TOKENS["supervisor"],"t1","supervisor"),
            (TOKENS["t2"],"t2","supervisor"),
        ]
    ]}),encoding="utf-8")
    policy.chmod(0o600)
    spy=AMISpy()
    tracker=QueueMemberTracker()
    monkeypatch.setattr(server,"QUEUE_ACCESS_POLICY_PATH",str(policy))
    monkeypatch.setattr(server,"QUEUE_CORS_ORIGINS",{ORIGIN})
    monkeypatch.setattr(server,"QUEUE_MEMBER_MUTATIONS_ENABLED",True)
    monkeypatch.setattr(server,"QUEUE_MEMBER_ALLOWED_EXTENSIONS",[
        "t1-recepcao","t1-recepcao-2","t2-recepcao",
    ])
    monkeypatch.setattr(server,"queue_member_tracker",tracker)
    monkeypatch.setattr(server,"ami",spy)
    http=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
    thread=threading.Thread(target=http.serve_forever,daemon=True)
    thread.start()
    try:
        yield http.server_address[1],spy,tracker
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=3)


def test_anonymous_and_cross_origin_denied_before_ami(service):
    port, spy, _ = service
    data={"queue":"fila-t1","extension":"t1-recepcao"}
    assert request(port,"/api/queue/members/join",method="POST",data=data)[0]==401
    denied = request(port,"/api/queue/members/join",method="POST",
                     token=TOKENS["agent"],data=data,origin="https://evil.invalid")
    assert denied[0]==403
    assert "Access-Control-Allow-Origin" not in denied[1]
    assert spy.actions==[]


def test_mutation_opt_in_disabled_even_with_supervisor(service,monkeypatch):
    port, spy, _=service
    monkeypatch.setattr(server,"QUEUE_MEMBER_MUTATIONS_ENABLED",False)
    code, _, payload=request(port,"/api/queue/members/join",method="POST",
                              token=TOKENS["supervisor"],data={
                                "queue":"fila-t1","extension":"t1-recepcao",
                              })
    assert code==503 and spy.actions==[]
    assert b"desabilitadas" in payload


def test_agent_self_service_queue_join_and_leave(service):
    port,spy,tracker=service
    join={"queue":"fila-t1-en","extension":"t1-recepcao",
          "penalty":5,"paused":True}
    code,head,raw=request(port,"/api/queue/members/join",method="POST",
                          token=TOKENS["agent"],data=join,origin=ORIGIN)
    assert code==202
    assert head["Access-Control-Allow-Origin"]==ORIGIN
    assert head["Cache-Control"]=="no-store"
    assert spy.actions[0]["Action"]=="QueueAdd"
    assert spy.actions[0]["Penalty"]=="5"
    assert json.loads(raw)["ami_event_confirmed"] is False
    # ACK não inventa evento nem cria estado autoritativo.
    assert tracker.snapshot({"tenant":"t1","role":"supervisor"})["members"]==[]
    leave={"queue":"fila-t1-en","extension":"t1-recepcao"}
    code,_,_=request(port,"/api/queue/members/leave",method="POST",
                      token=TOKENS["agent"],data=leave)
    assert code==202
    assert spy.actions[-1]=={
        "Action":"QueueRemove","Queue":"fila-t1-en",
        "Interface":"PJSIP/t1-recepcao"
    }


def test_supervisor_and_agent_roles_enforced(service):
    port,spy,_=service
    other_agent={"queue":"fila-t1","extension":"t1-recepcao-2"}
    code,_,_=request(port,"/api/queue/members/join",method="POST",
                      token=TOKENS["agent"],data=other_agent)
    assert code==403
    code,_,_=request(port,"/api/queue/members/join",method="POST",
                      token=TOKENS["supervisor"],data=other_agent)
    assert code==202
    assert len(spy.actions)==1


@pytest.mark.parametrize("queue,ext",[
    ("fila-t2","t1-recepcao"),("fila-t10","t1-recepcao"),
    ("fila-t1","t2-recepcao"),("fila-t1-en-evil","t1-recepcao"),
])
def test_cross_tenant_rejected_without_ami(service,queue,ext):
    port,spy,_=service
    code,_,_=request(port,"/api/queue/members/join",method="POST",
                      token=TOKENS["supervisor"],data={
                        "queue":queue,"extension":ext
                      })
    assert code==403 and spy.actions==[]


def test_pause_one_queue_and_resume_ami_actions(service):
    port,spy,_=service
    for paused,reason in [(True,"treinamento"),(False,"")]:
        code,_,_=request(port,"/api/queue/members/pause",method="POST",
                          token=TOKENS["agent"],data={
                            "queue":"fila-t1-es","extension":"t1-recepcao",
                            "paused":paused,"reason":reason
                          })
        assert code==202
    assert spy.actions[0]["Queue"]=="fila-t1-es"
    assert spy.actions[0]["Action"]=="QueuePause"
    assert spy.actions[0]["Reason"]=="treinamento"
    assert spy.actions[1]["Paused"]=="false"
    assert "Reason" not in spy.actions[1]


def test_failure_ami_does_not_claim_success(service):
    port, spy,tracker=service
    spy.response={"Response":"Error","Message":"not found"}
    code,_,raw=request(port,"/api/queue/members/leave",method="POST",
                        token=TOKENS["supervisor"],data={
                          "queue":"fila-t1", "extension":"t1-recepcao",
                        })
    assert code==502
    assert b"not found" not in raw
    assert tracker.snapshot({"tenant":"t1","role":"supervisor"})["members"]==[]


def test_memory_tracker_read_scope_ignores_query_tenant_and_agents_only_self(service):
    port,_,tracker=service
    for queue,ext in [
        ("fila-t1","t1-recepcao"),("fila-t1-es","t1-recepcao-2"),
        ("fila-t2","t2-recepcao"),
    ]:
        tracker.apply_event({"Event":"QueueMemberAdded","Queue":queue,
                             "Interface":"PJSIP/"+ext, "Membership":"dynamic"})
    for token,expected in [
        (TOKENS["agent"],["t1-recepcao"]),
        (TOKENS["supervisor"],["t1-recepcao","t1-recepcao-2"]),
        (TOKENS["t2"],["t2-recepcao"]),
    ]:
        code,head,raw=request(port,"/api/queue/members?tenant=t10",token=token,origin=ORIGIN)
        assert code==200
        body=json.loads(raw)
        assert sorted(x["extension"] for x in body["members"])==expected
        assert body["complete_membership_inventory"] is False
        assert head["Cache-Control"]=="no-store"


def test_nonexistent_mutation_path_not_open(service):
    port,spy,_=service
    code,_,_=request(port,"/api/queue/members/joinX",method="POST",
                      token=TOKENS["supervisor"],data={})
    assert code==404 and spy.actions==[]


def test_malformed_json_duplicate_keys_denied_without_ami(service):
    port,spy,_=service
    raw=b'{"queue":"fila-t1","extension":"t1-recepcao","extension":"t2-recepcao"}'
    code,_,_=request(port,"/api/queue/members/join",method="POST",
                      token=TOKENS["supervisor"],raw=raw,
                      headers={"Content-Type":"application/json"})
    assert code==400 and spy.actions==[]


def test_wrong_content_type_denied(service):
    port,spy,_=service
    code,_,_=request(port,"/api/queue/members/join",method="POST",
                      token=TOKENS["supervisor"],raw=b"{}",
                      headers={"Content-Type":"text/plain"})
    assert code==415 and spy.actions==[]


def test_explicit_options_with_cors(service):
    port,spy,_=service
    code,head,_=request(port,"/api/queue/members/join",method="OPTIONS",origin=ORIGIN)
    assert code==204
    assert head["Access-Control-Allow-Origin"]==ORIGIN
    code,_,_=request(port,"/api/queue/members/join",method="OPTIONS",
                       origin="https://attacker.invalid")
    assert code==403 and spy.actions==[]
