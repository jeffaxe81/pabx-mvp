"""Negative controls for concurrent outbound attempts and ambiguous AMI events."""
import re

import server
from campaigns import create_campaign, load_campaigns, mark_contact_calling
from callbacks import add_callback_request, load_callbacks, mark_callback_calling


def _dial_event(tenant="t1", number="11999998888", attempt_id=None):
    event = {"Event": "DialEnd", "AccountCode": tenant, "DialStatus": "ANSWER",
             "Dialstring": "PJSIP/" + number + "@gateway-tdm"}
    if attempt_id is not None:
        event["AttemptID"] = attempt_id
    return event


def test_attempt_ids_are_unique_persisted_and_repeat_claims_are_denied(tmp_path):
    campaigns = tmp_path / "campaigns.json"
    callbacks = tmp_path / "callbacks.json"
    ok, _, campaign = create_campaign(campaigns, {
        "tenant": "t1", "name": "A", "agent_extension": "t1-recepcao",
        "contacts": ["(11) 99999-8888", "11999998888"],
    })
    assert ok and len(campaign["contacts"]) == 1
    number = "11999998888"
    assert mark_contact_calling(campaigns, campaign["id"], number)[0]
    assert not mark_contact_calling(campaigns, campaign["id"], number)[0]
    c_attempt = load_campaigns(campaigns)[0]["contacts"][0]["attempt_id"]
    assert re.fullmatch("[a-f0-9]{32}", c_attempt)
    entry = add_callback_request(callbacks, number, tenant="t1")
    assert mark_callback_calling(callbacks, entry["id"])[0]
    assert not mark_callback_calling(callbacks, entry["id"])[0]
    b_attempt = load_callbacks(callbacks)[0]["attempt_id"]
    assert re.fullmatch("[a-f0-9]{32}", b_attempt)
    assert c_attempt != b_attempt


def test_same_tenant_same_phone_multiple_campaigns_fails_closed(tmp_path, monkeypatch):
    path = tmp_path / "campaigns.json"
    monkeypatch.setattr(server, "CAMPAIGNS_PATH", str(path))
    names = ["primeira", "segunda"]
    campaigns = []
    for name in names:
        ok, _, campaign = create_campaign(path, {
            "tenant": "t1", "name": name, "agent_extension": "t1-recepcao",
            "contacts": ["11999998888"],
        })
        assert ok
        assert mark_contact_calling(path, campaign["id"], "11999998888")[0]
        campaigns.append(campaign)

    server.apply_campaign_dial_result(_dial_event())
    records = load_campaigns(path)
    assert all(c["contacts"][0]["status"] == "discando" for c in records)

    attempt_id = records[1]["contacts"][0]["attempt_id"]
    server.apply_campaign_dial_result(_dial_event(attempt_id=attempt_id))
    records = load_campaigns(path)
    assert records[0]["contacts"][0]["status"] == "discando"
    assert records[1]["contacts"][0]["status"] == "atendida"


def test_same_tenant_same_phone_multiple_callbacks_fails_closed(tmp_path, monkeypatch):
    path = tmp_path / "callbacks.json"
    monkeypatch.setattr(server, "CALLBACKS_PATH", str(path))
    for _ in range(2):
        callback = add_callback_request(path, "11999998888", tenant="t1")
        assert mark_callback_calling(path, callback["id"])[0]

    server.apply_callback_dial_result(_dial_event())
    records = load_callbacks(path)
    assert all(c["status"] == "discando" for c in records)

    attempt_id = records[1]["attempt_id"]
    server.apply_callback_dial_result(_dial_event(attempt_id=attempt_id))
    records = load_callbacks(path)
    assert records[0]["status"] == "discando"
    assert records[1]["status"] == "concluido"
