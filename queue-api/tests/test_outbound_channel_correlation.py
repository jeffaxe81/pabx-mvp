"""AMI OriginateResponse and DialEnd correlated to the channel actually created."""
import server
from campaigns import create_campaign, load_campaigns, mark_contact_calling
from callbacks import add_callback_request, load_callbacks, mark_callback_calling
from outbound_correlation import channel_id_for, matches_dial_event


NUMBER = "11999998888"


def _event(tenant="t1", uniqueid=None, attempt_id=None, disposition="ANSWER"):
    event = {"Event": "DialEnd", "AccountCode": tenant,
             "DialStatus": disposition, "Dialstring": "PJSIP/" + NUMBER + "@gateway-tdm"}
    if uniqueid is not None:
        event["Uniqueid"] = uniqueid
    if attempt_id is not None:
        event["AttemptID"] = attempt_id
    return event


def _originate(attempt, channel, response="Success", tenant=None):
    event = {"Event": "OriginateResponse", "ActionID": attempt,
             "Uniqueid": channel, "Response": response}
    if tenant is not None:
        event["AccountCode"] = tenant
    return event


def test_campaign_uniqueid_reconciles_only_matching_attempt(tmp_path, monkeypatch):
    campaigns = tmp_path / "campaigns.json"
    callbacks = tmp_path / "callbacks.json"
    monkeypatch.setattr(server, "CAMPAIGNS_PATH", str(campaigns))
    monkeypatch.setattr(server, "CALLBACKS_PATH", str(callbacks))
    for name in ("left", "right"):
        ok, _, record = create_campaign(campaigns, {
            "name": name, "tenant": "t1", "agent_extension": "t1-recepcao",
            "contacts": [NUMBER],
        })
        assert ok
        assert mark_contact_calling(campaigns, record["id"], NUMBER)[0]
    records = load_campaigns(campaigns)
    first, second = [c["contacts"][0] for c in records]
    assert first["channel_id"] == channel_id_for(first["attempt_id"])
    assert second["channel_id"] == channel_id_for(second["attempt_id"])
    assert first["channel_id"] != second["channel_id"]

    server.apply_originate_response(_originate(second["attempt_id"], first["channel_id"]))
    assert all(not c["contacts"][0].get("originate_response") for c in load_campaigns(campaigns))

    server.apply_originate_response(_originate(second["attempt_id"], second["channel_id"]))
    updated = load_campaigns(campaigns)
    assert updated[1]["contacts"][0]["originate_response"] == "Success"
    assert not updated[0]["contacts"][0].get("originate_response")

    server.apply_campaign_dial_result(_event(uniqueid="axi-bogus"))
    assert all(c["contacts"][0]["status"] == "discando" for c in load_campaigns(campaigns))
    server.apply_campaign_dial_result(_event(uniqueid=second["channel_id"]))
    assert load_campaigns(campaigns)[1]["contacts"][0]["status"] == "atendida"
    assert load_campaigns(campaigns)[0]["contacts"][0]["status"] == "discando"


def test_callback_exact_uniqueid_prevents_cross_kind_and_cross_tenant(tmp_path, monkeypatch):
    campaign_path = tmp_path / "campaigns.json"
    callback_path = tmp_path / "callbacks.json"
    monkeypatch.setattr(server, "CAMPAIGNS_PATH", str(campaign_path))
    monkeypatch.setattr(server, "CALLBACKS_PATH", str(callback_path))
    ok, _, campaign = create_campaign(campaign_path, {
        "name": "same number", "tenant": "t1",
        "agent_extension": "t1-recepcao", "contacts": [NUMBER],
    })
    assert ok and mark_contact_calling(campaign_path, campaign["id"], NUMBER)[0]
    cb1 = add_callback_request(callback_path, NUMBER, tenant="t1")
    cb2 = add_callback_request(callback_path, NUMBER, tenant="t2")
    assert mark_callback_calling(callback_path, cb1["id"])[0]
    assert mark_callback_calling(callback_path, cb2["id"])[0]
    first = next(x for x in load_callbacks(callback_path) if x["tenant"] == "t1")
    second = next(x for x in load_callbacks(callback_path) if x["tenant"] == "t2")
    assert first["channel_id"] != second["channel_id"]
    server.apply_originate_response(_originate(first["attempt_id"], first["channel_id"], tenant="t2"))
    assert load_callbacks(callback_path)[0].get("originate_response") is None
    server.apply_originate_response(_originate(first["attempt_id"], first["channel_id"], tenant="t1"))
    assert load_callbacks(callback_path)[0]["originate_response"] == "Success"

    # Same phone is active in campaign AND callback for tenant t1.
    # Only channel identity can resolve a DialEnd without AttemptID.
    server.apply_campaign_dial_result(_event(uniqueid=first["channel_id"]))
    server.apply_callback_dial_result(_event(uniqueid=first["channel_id"]))
    assert load_callbacks(callback_path)[0]["status"] == "concluido"
    assert load_campaigns(campaign_path)[0]["contacts"][0]["status"] == "discando"
    assert load_callbacks(callback_path)[1]["status"] == "discando"

    # Wrong tenant source must not touch the other tenant.
    server.apply_callback_dial_result(_event(tenant="t1", uniqueid=second["channel_id"]))
    assert load_callbacks(callback_path)[1]["status"] == "discando"
    server.apply_callback_dial_result(_event(tenant="t2", uniqueid=second["channel_id"]))
    assert load_callbacks(callback_path)[1]["status"] == "concluido"


def test_failed_originate_keeps_claim_in_manual_review_state(tmp_path, monkeypatch):
    callbacks = tmp_path / "callbacks.json"
    monkeypatch.setattr(server, "CALLBACKS_PATH", str(callbacks))
    monkeypatch.setattr(server, "CAMPAIGNS_PATH", str(tmp_path / "campaigns.json"))
    cb = add_callback_request(callbacks, NUMBER, tenant="t1")
    assert mark_callback_calling(callbacks, cb["id"])[0]
    record = load_callbacks(callbacks)[0]
    server.apply_originate_response(_originate(record["attempt_id"], record["channel_id"], response="Failure"))
    assert load_callbacks(callbacks)[0]["originate_response"] == "Failure"
    server.apply_callback_dial_result(_event(uniqueid=record["channel_id"]))
    assert load_callbacks(callbacks)[0]["status"] == "discando"
    # Conflicting late success is ignored.
    server.apply_originate_response(_originate(record["attempt_id"], record["channel_id"], response="Success"))
    assert load_callbacks(callbacks)[0]["originate_response"] == "Failure"


def test_dial_end_cannot_override_mismatched_uniqueid_even_with_valid_attempt_hint():
    record = {"attempt_id": "a" * 32, "channel_id": "axe-" + "a" * 32}
    assert not matches_dial_event({"AttemptID": "a" * 32, "Uniqueid": "another"}, record)
    assert matches_dial_event({"AttemptID": "a" * 32}, record)
    assert matches_dial_event({"DestUniqueid": "axe-" + "a" * 32}, record)
    assert not matches_dial_event({}, record)
    assert not matches_dial_event({"Uniqueid": "axe-" + "b" * 32}, record)
    assert channel_id_for("invalid") is None
