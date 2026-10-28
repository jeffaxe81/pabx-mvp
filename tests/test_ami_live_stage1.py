"""Regressões do perfil AMI descartável e da avaliação fail-closed."""
from pathlib import Path
import re

from lab.ami_live_checks import assess_response, prepare_ami, required_ami_checks


ATTEMPT = "a" * 32
CHANNEL = "axe-" + ATTEMPT


def event(**overrides):
    value = {
        "Event": "OriginateResponse", "ActionID": ATTEMPT,
        "Uniqueid": CHANNEL, "Response": "Success", "AccountCode": "t1",
    }
    value.update(overrides)
    return value


def test_real_event_shape_and_negative_identity_controls():
    result = assess_response(event(), ATTEMPT, CHANNEL)
    assert all(result.values())
    assert result["ami_action_channel_correlated"]
    assert result["ami_originate_success"]
    assert set(result) == required_ami_checks() - {"ami_login", "ami_action_queued"}


def test_wrong_account_channel_or_action_cannot_pass():
    for bad in ({"ActionID": "b" * 32}, {"Uniqueid": "axe-" + "b" * 32},
                {"AccountCode": "t2"}, {"Response": "Failure"},
                {"Event": "Hangup"}):
        result = assess_response(event(**bad), ATTEMPT, CHANNEL)
        assert not all(result.values())
        assert not result["ami_originate_success"]


def test_ami_profile_has_only_loopback_and_ephemeral_credential(tmp_path):
    conf = tmp_path / "asterisk"
    conf.mkdir()
    (conf / "extensions.conf").write_text("[original]\nexten => s,1,Hangup()\n")
    prepared = {"conf": conf}
    prepare_ami(prepared)
    manager = (conf / "manager.conf").read_text()
    dialplan = (conf / "extensions.conf").read_text()
    assert "enabled=yes" in manager
    assert "bindaddr=127.0.0.1" in manager
    assert "permit=127.0.0.1/255.255.255.255" in manager
    assert "deny=0.0.0.0/0.0.0.0" in manager
    assert "troque_esta_senha" not in manager
    assert re.fullmatch(r"[0-9a-f]{64}", prepared["ami_secret"])
    assert prepared["ami_secret"] in manager
    assert not (Path(conf / "manager.conf").stat().st_mode & 0o077)
    assert "[axe-ami-lab]" in dialplan
    assert "Dial(Local/target@axe-ami-lab/n,4)" in dialplan
    assert dialplan.count("Local/") == 1  # somente a perna Local descartável do laboratório
    assert "gateway-tdm" not in dialplan
    assert "PJSIP/" not in dialplan
