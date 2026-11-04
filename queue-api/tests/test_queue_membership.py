"""Testes das ações operacionais de membros; sem Asterisk de produção."""
import copy
import pytest

from queue_membership import (
    QueueMemberTracker, validate_member_change, member_ami_action, valid_queue
)

AGENT = {"tenant": "t1", "role": "agent", "extension": "t1-recepcao"}
SUPERVISOR = {"tenant": "t1", "role": "supervisor"}
OTHER = {"tenant": "t10", "role": "supervisor"}
ALLOWED = ["t1-recepcao", "t1-recepcao-2", "t10-recepcao"]


def request(operation="join", principal=AGENT, **override):
    body = {"queue": "fila-t1", "extension": "t1-recepcao"}
    body.update(override)
    return validate_member_change(body, principal, ALLOWED, operation)


def test_agent_can_join_own_default_queue():
    ok, error, data = request()
    assert ok and error is None
    assert data == {
        "queue": "fila-t1", "extension": "t1-recepcao",
        "penalty": 0, "paused": False
    }
    assert member_ami_action(data, "join") == {
        "Action": "QueueAdd", "Queue": "fila-t1",
        "Interface": "PJSIP/t1-recepcao", "Penalty": "0", "Paused": "false",
        "MemberName": "t1-recepcao", "StateInterface": "PJSIP/t1-recepcao",
    }


def test_supervisor_can_join_colleague_but_agent_cannot():
    assert request(principal=SUPERVISOR, extension="t1-recepcao-2")[0]
    assert not request(principal=AGENT, extension="t1-recepcao-2")[0]


def test_join_penalty_and_initial_pause():
    ok, _, data = request(queue="fila-t1-en", penalty=8, paused=True)
    assert ok
    action = member_ami_action(data, "join")
    assert action["Penalty"] == "8"
    assert action["Paused"] == "true"
    assert action["Queue"] == "fila-t1-en"


def test_leave_queue_generates_exact_action_without_global_effect():
    ok, _, data = request("leave")
    assert ok
    action = member_ami_action(data, "leave")
    assert action == {
        "Action": "QueueRemove", "Queue": "fila-t1",
        "Interface": "PJSIP/t1-recepcao",
    }


@pytest.mark.parametrize("paused,reason", [(True, "almoco"), (False, "")])
def test_pause_and_resume_one_queue_only(paused, reason):
    ok, _, data = request("pause", queue="fila-t1-es",
                          paused=paused, reason=reason)
    assert ok
    action = member_ami_action(data, "pause")
    assert action["Action"] == "QueuePause"
    assert action["Queue"] == "fila-t1-es"
    assert action["Paused"] == ("true" if paused else "false")
    assert ("Reason" in action) == paused


@pytest.mark.parametrize("queue", [
    "fila-t2", "fila-t10", "fila-t1-unknown", "fila-t1-",
    "fila-t1-en-other", "fila-t1\nAction: Originate", "fila-t01",
    "fila-t1 ", None, 42, ["fila-t1"], "fila-t1-en\n",
])
def test_rejects_cross_tenant_or_invalid_queue(queue):
    assert request(queue=queue)[0] is False


@pytest.mark.parametrize("extension", [
    "t2-recepcao", "t10-recepcao", "t1-ghost",
    "PJSIP/t1-recepcao", "t1-recepcao\r\nAction: Originate",
    None, 1, False, ["t1-recepcao"],
])
def test_rejects_wrong_or_unauthorized_extension(extension):
    assert request(extension=extension)[0] is False


@pytest.mark.parametrize("penalty", [
    -1, 11, 1.1, "1", True, None, float("nan"), float("inf"),
])
def test_rejects_bad_penalty(penalty):
    assert request(penalty=penalty)[0] is False


@pytest.mark.parametrize("paused", [1, 0, "true", None, [], 0.1])
def test_rejects_non_boolean_pause(paused):
    assert request(paused=paused)[0] is False
    assert request("pause", paused=paused, reason="almoco")[0] is False


@pytest.mark.parametrize("reason", [
    None, "", " ", "hi\r\nAction: Originate",
    "foo:bar", "x" * 81, 42, {},
])
def test_pause_requires_sanitized_reason(reason):
    assert request("pause", paused=True, reason=reason)[0] is False


def test_resume_rejects_reason_and_join_rejects_extra_fields():
    assert request("pause", paused=False, reason="almoco")[0] is False
    assert request(untrusted="password")[0] is False
    assert request("leave", penalty=3)[0] is False
    assert request("pause", paused=True, reason="treinamento", penalty=3)[0] is False


def test_empty_policy_or_broken_principal_cannot_mutate():
    assert not validate_member_change({"queue":"fila-t1", "extension":"t1-recepcao"},
                                      {}, ALLOWED, "join")[0]
    assert not validate_member_change({"queue":"fila-t1", "extension":"t1-recepcao"},
                                      AGENT, [], "join")[0]


def test_tracker_tracks_valid_added_pause_removed_and_does_not_guess_status():
    tracker = QueueMemberTracker()
    assert tracker.snapshot(SUPERVISOR)["members"] == []
    tracker.apply_event({"Event":"QueueMemberPause", "Queue":"fila-t1",
                         "Interface":"PJSIP/t1-recepcao", "Paused":"1"})
    assert tracker.snapshot(SUPERVISOR)["members"] == []
    tracker.apply_event({"Event":"QueueMemberAdded","Queue":"fila-t1",
                         "Interface":"PJSIP/t1-recepcao","Membership":"dynamic",
                         "Penalty":"7","Paused":"0","Status":"1"})
    first = tracker.snapshot(SUPERVISOR)
    assert first["scope"] == "observed_ami_events_only"
    assert first["complete_membership_inventory"] is False
    assert first["members"] == [{
        "queue":"fila-t1","extension":"t1-recepcao",
        "membership":"dynamic", "paused":False,
        "penalty":7, "device_status":1,
    }]
    tracker.apply_event({"Event":"QueueMemberPause", "Queue":"fila-t1",
                         "Interface":"PJSIP/t1-recepcao", "Paused":"1"})
    assert tracker.snapshot(SUPERVISOR)["members"][0]["paused"] is True
    tracker.apply_event({"Event":"QueueMemberRemoved", "Queue":"fila-t1",
                         "Interface":"PJSIP/t1-recepcao"})
    assert tracker.snapshot(SUPERVISOR)["members"] == []


def test_tracker_isolation_t1_t10_t2_and_agent_self_view():
    tracker = QueueMemberTracker()
    for tenant, extension in (("t1","t1-recepcao"),
                              ("t1","t1-recepcao-2"),
                              ("t10","t10-recepcao"),
                              ("t2","t2-recepcao")):
        tracker.apply_event({"Event":"QueueMemberAdded", "Queue":"fila-"+tenant,
                             "Interface":"PJSIP/"+extension, "Membership":"static"})
    view = tracker.snapshot(SUPERVISOR)
    assert set(x["extension"] for x in view["members"]) == {
        "t1-recepcao", "t1-recepcao-2",
    }
    assert [x["extension"] for x in tracker.snapshot(AGENT)["members"]] == ["t1-recepcao"]
    assert [x["extension"] for x in tracker.snapshot(OTHER)["members"]] == ["t10-recepcao"]


def test_tracker_rejects_poisoned_queue_and_cross_tenant_events():
    tracker = QueueMemberTracker()
    for row in [
        {"Event":"QueueMemberAdded", "Queue":"fila-t1",
         "Interface":"PJSIP/t2-recepcao"},
        {"Event":"QueueMemberAdded", "Queue":"fila-t1XYZ",
         "Interface":"PJSIP/t1-recepcao"},
        {"Event":"QueueMemberAdded", "Queue":"fila-t1",
         "Interface":"Local/t1-recepcao"},
        {"Event":"QueueMemberAdded", "Queue":"fila-t1",
         "Interface":"PJSIP/t1-recepcao\r\nAction: Originate"},
        {"Event":"QueueMemberRemoved", "Queue":"fila-t1",
         "Interface":"PJSIP/t1-recepcao"},
    ]:
        tracker.apply_event(row)
    assert tracker.snapshot(SUPERVISOR)["members"] == []


def test_snapshot_returns_copies_and_never_accepts_spoofed_tenant():
    tracker = QueueMemberTracker()
    event = {"Event":"QueueMemberAdded", "Queue":"fila-t1",
             "Interface":"PJSIP/t1-recepcao"}
    tracker.apply_event(event)
    snapshot = tracker.snapshot(SUPERVISOR)
    snapshot["members"][0]["paused"] = True
    assert tracker.snapshot(SUPERVISOR)["members"][0]["paused"] is None
    with pytest.raises(ValueError):
        tracker.snapshot({"tenant":"t1", "role":"agent", "extension":"t10-recepcao"})


def test_tracker_has_bounded_capacity_and_validates_constructor():
    with pytest.raises(ValueError):
        QueueMemberTracker(0)
    tracker = QueueMemberTracker(capacity=1)
    for ext in ("t1-recepcao", "t1-recepcao-2"):
        tracker.apply_event({"Event":"QueueMemberAdded","Queue":"fila-t1",
                             "Interface":"PJSIP/"+ext})
    assert len(tracker.snapshot(SUPERVISOR)["members"]) == 1


def test_tracker_unknown_fields_do_not_poison_safe_snapshot():
    tracker = QueueMemberTracker()
    tracker.apply_event({"Event":"QueueMemberAdded", "Queue":"fila-t1",
                         "Interface":"PJSIP/t1-recepcao",
                         "MemberName":"PRIVATE-NAME",
                         "Status":"999999", "Penalty":True,
                         "Paused":"true"})
    assert "PRIVATE" not in str(tracker.snapshot(SUPERVISOR))
    assert tracker.snapshot(SUPERVISOR)["members"][0]["device_status"] is None
