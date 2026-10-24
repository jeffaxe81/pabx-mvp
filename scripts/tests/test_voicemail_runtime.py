"""Contrato estrito de isolamento do *97 no Asterisk real."""
import pytest

from lab.voicemail_checks import (
    inspected_voicemail_channel, required_voicemail_checks, CASES,
)
from lab.asterisk_lab import summarize


def test_exact_mailbox_requires_single_matching_channel_row():
    correct = ("PJSIP/t1-1001-00000001!t1-internal!*97!5!Up!"
               "VoiceMailMain!t1-1001@t1!123.1")
    assert inspected_voicemail_channel(correct, "t1-1001", "t1") == {
        "exact": True, "no_foreign": True,
    }


@pytest.mark.parametrize("line", [
    "PJSIP/t1-1001-00000001!t1-internal!*97!5!Up!VoiceMailMain!t2-1001@t2!",
    "PJSIP/t1-1001-00000001!t1-internal!*97!5!Up!VoiceMailMain!t1-1002@t1!",
    "PJSIP/t1-1001-00000001!t1-internal!*97!5!Up!VoiceMailMain!!",
    "PJSIP/t1-1001-00000001!t1-internal!*97!5!Up!Hangup!t1-1001@t1!",
    "PJSIP/t10-1001-00000001!t10-internal!*97!5!Up!VoiceMailMain!t1-1001@t1!",
    "PJSIP/t2-1001-00000001!t2-internal!*97!5!Up!VoiceMailMain!t1-1001@t1!",
    "garbage",
    "",
])
def test_forged_or_unrelated_mailbox_not_accepted(line):
    assert not inspected_voicemail_channel(line, "t1-1001", "t1")["exact"]


def test_mixed_good_and_foreign_rows_cannot_be_accepted():
    correct = "PJSIP/t1-1001-a!t1-internal!*97!5!Up!VoiceMailMain!t1-1001@t1!"
    foreign = "PJSIP/t1-1001-b!t1-internal!*97!5!Up!VoiceMailMain!t2-1001@t2!"
    result = inspected_voicemail_channel(correct + "\n" + foreign, "t1-1001", "t1")
    assert result == {"exact": True, "no_foreign": False}


def test_rejects_oversized_cli_output():
    assert inspected_voicemail_channel("x" * (1024 * 1024 + 1), "t1-1001", "t1") == {
        "exact": False, "no_foreign": False
    }


def test_summary_requires_all_three_tenants_and_does_not_grant_go():
    base = {"real_runtime", "tls_transport", "wss_transport", "container_removed",
            "checkout_clean", "runtime_mounts", "source_label"}
    base |= {f"{name}:{tenant}" for name in (
        "context", "register", "contact", "unregister", "wrong_password"
    ) for tenant in ("t1", "t2", "t3")}
    from lab.call_checks import required_call_checks
    full = {name: True for name in base | required_call_checks() | required_voicemail_checks()}
    assert summarize(full, calls=True, voicemail=True)["success"] is True
    assert summarize(full, calls=True, voicemail=False)["success"] is False
    assert summarize({name: value for name, value in full.items()
                      if name != "vm_exact_mailbox:t3"}, calls=True, voicemail=True)["success"] is False
    assert summarize({**full, "vm_no_foreign_mailbox:t1": False},
                     calls=True, voicemail=True)["success"] is False
    assert len(CASES) == 3


def test_cli_voicemail_mode_requires_call_mode(tmp_path):
    from lab.asterisk_lab import main
    with pytest.raises(SystemExit) as error:
        main(["--voicemail", "--report", str(tmp_path / "report.json")])
    assert error.value.code != 0
