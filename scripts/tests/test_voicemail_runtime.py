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
    assert result == {"exact": False, "no_foreign": False}


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


@pytest.mark.parametrize("bad", [
    "PJSIP/t1-1001-00000001!t2-internal!*97!5!Up!VoiceMailMain!t1-1001@t1!",
    "PJSIP/t1-1001-00000001!t1-internal!1000!5!Up!VoiceMailMain!t1-1001@t1!",
    "PJSIP/t1-1001-nothex!t1-internal!*97!5!Up!VoiceMailMain!t1-1001@t1!",
    "PJSIP/t1-10010-00000001!t1-internal!*97!5!Up!VoiceMailMain!t1-1001@t1!",
])
def test_mailbox_context_extension_and_exact_channel_must_match(bad):
    assert inspected_voicemail_channel(bad, "t1-1001", "t1") == {
        "exact": False, "no_foreign": False,
    }


def test_duplicate_channel_evidence_cannot_pass_by_combination():
    valid = "PJSIP/t1-1001-00000001!t1-internal!*97!5!Up!VoiceMailMain!t1-1001@t1!"
    duplicated = valid.replace("00000001", "00000002")
    assert inspected_voicemail_channel(valid + "\n" + duplicated,
                                       "t1-1001", "t1") == {
        "exact": False, "no_foreign": False,
    }


@pytest.mark.parametrize("endpoint,tenant", [
    ("t1-1001", "t10"), ("t10-1001", "t1"), ("bad-name", "t1"),
    (None, "t1"), ("t1-1001", None),
])
def test_mismatched_identity_fails_closed(endpoint, tenant):
    good = "PJSIP/t1-1001-00000001!t1-internal!*97!5!Up!VoiceMailMain!t1-1001@t1!"
    assert inspected_voicemail_channel(good, endpoint, tenant) == {
        "exact": False, "no_foreign": False,
    }

@pytest.mark.parametrize("channel_state", ["Ring", "Down", "Ringing", "", "Busy"])
def test_voicemail_route_requires_live_up_channel(channel_state):
    row = ("PJSIP/t1-1001-00000001!t1-internal!*97!5!" +
           channel_state + "!VoiceMailMain!t1-1001@t1!123.1")
    assert inspected_voicemail_channel(row, "t1-1001", "t1") == {
        "exact": False, "no_foreign": False,
    }

def test_voicemail_dtmf_transport_requires_separate_evidence_and_no_pin_claim():
    from lab.voicemail_checks import required_voicemail_dtmf_checks
    from lab.call_checks import required_call_checks
    basic = {'real_runtime', 'tls_transport', 'wss_transport',
             'container_removed', 'checkout_clean', 'runtime_mounts', 'source_label'}
    basic |= {f'{name}:{tenant}' for name in (
        'context', 'register', 'contact', 'unregister', 'wrong_password'
    ) for tenant in ('t1', 't2', 't3')}
    base = basic | required_call_checks() | required_voicemail_checks()
    full = {key: True for key in base | required_voicemail_dtmf_checks()}
    assert summarize(full, calls=True, voicemail=True, voicemail_dtmf=True)['success']
    for missing in required_voicemail_dtmf_checks():
        incomplete = {key: value for key, value in full.items() if key != missing}
        assert not summarize(incomplete, calls=True, voicemail=True,
                             voicemail_dtmf=True)['success']
    assert len(required_voicemail_dtmf_checks()) == 6


def test_voicemail_dtmf_mode_requires_calls_and_voicemail(tmp_path):
    from lab.asterisk_lab import main
    import pytest
    for flags in (['--voicemail-dtmf'], ['--calls', '--voicemail-dtmf'],
                  ['--voicemail', '--voicemail-dtmf']):
        with pytest.raises(SystemExit) as error:
            main([*flags, '--report', str(tmp_path / 'dtmf.json')])
        assert error.value.code != 0
