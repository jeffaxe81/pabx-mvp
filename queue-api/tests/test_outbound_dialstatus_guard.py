"""Unknown/invalid AMI DialEnd statuses must never release an outbound claim.

These are in-memory/temporary-file regressions; they are not proof that
ChannelId/Uniqueid are emitted by the deployed Asterisk version.
"""
import pytest

import server
from callbacks import add_callback_request, load_callbacks, mark_callback_calling
from campaigns import create_campaign, load_campaigns, mark_contact_calling


NUMBER = "11999998888"


def _claim(tmp_path, monkeypatch, kind):
    campaign_path = tmp_path / "campaigns.json"
    callback_path = tmp_path / "callbacks.json"
    monkeypatch.setattr(server, "CAMPAIGNS_PATH", str(campaign_path))
    monkeypatch.setattr(server, "CALLBACKS_PATH", str(callback_path))
    if kind == "campaign":
        ok, _, campaign = create_campaign(campaign_path, {
            "name": "teste", "tenant": "t1",
            "agent_extension": "t1-recepcao", "contacts": [NUMBER],
        })
        assert ok
        assert mark_contact_calling(campaign_path, campaign["id"], NUMBER)[0]
        target = load_campaigns(campaign_path)[0]["contacts"][0]
        apply_result = server.apply_campaign_dial_result
        load_target = lambda: load_campaigns(campaign_path)[0]["contacts"][0]
    else:
        callback = add_callback_request(callback_path, NUMBER, tenant="t1")
        assert callback is not None
        assert mark_callback_calling(callback_path, callback["id"])[0]
        target = load_callbacks(callback_path)[0]
        apply_result = server.apply_callback_dial_result
        load_target = lambda: load_callbacks(callback_path)[0]
    return target, apply_result, load_target


@pytest.mark.parametrize("kind", ["campaign", "callback"])
@pytest.mark.parametrize("bad_status", [None, "", "NOANSWERED", "ORIGINATE_ERROR", 1, {}, []])
def test_unrecognized_dial_status_does_not_complete_or_requeue(
    tmp_path, monkeypatch, kind, bad_status
):
    record, apply_result, load_target = _claim(tmp_path, monkeypatch, kind)
    before = dict(record)
    apply_result({
        "Event": "DialEnd", "AccountCode": "t1",
        "DialStatus": bad_status,
        "Uniqueid": record["channel_id"],
        "Dialstring": "PJSIP/" + NUMBER + "@gateway-tdm",
    })
    assert load_target() == before


@pytest.mark.parametrize("kind", ["campaign", "callback"])
def test_known_dial_status_with_matching_channel_is_still_accepted(
    tmp_path, monkeypatch, kind
):
    record, apply_result, load_target = _claim(tmp_path, monkeypatch, kind)
    apply_result({
        "Event": "DialEnd", "AccountCode": "t1",
        "DialStatus": "ANSWER",
        "Uniqueid": record["channel_id"],
        "Dialstring": "PJSIP/" + NUMBER + "@gateway-tdm",
    })
    assert load_target()["status"] == ("atendida" if kind == "campaign" else "concluido")


@pytest.mark.parametrize("kind", ["campaign", "callback"])
def test_known_status_with_different_channel_remains_pending(
    tmp_path, monkeypatch, kind
):
    _, apply_result, load_target = _claim(tmp_path, monkeypatch, kind)
    before = dict(load_target())
    apply_result({
        "Event": "DialEnd", "AccountCode": "t1",
        "DialStatus": "ANSWER",
        "Uniqueid": "axe-" + "0" * 32,
        "Dialstring": "PJSIP/" + NUMBER + "@gateway-tdm",
    })
    assert load_target() == before
