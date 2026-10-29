"""Regressões de isolamento do PIN efêmero do laboratório Asterisk."""
from pathlib import Path

from lab.voicemail_pin_checks import validate_prepared_voicemail
from lab.asterisk_lab import prepare
from lab.call_checks import prepare_calls
from lab.voicemail_checks import CASES


def sample():
    static = """[general]
format=wav
[t1]
t1-1001 => 12345679,T1
t1-1002 => 23456789,T1
t1-recepcao => 34567891,T1
t1-recepcao-2 => 45678912,T1
[t2]
t2-1001 => 56789123,T2
t2-recepcao => 67891234,T2
t2-recepcao-2 => 78912345,T2
"""
    dynamic = """[t3]
t3-1001 => 81235679,T3
t3-recepcao => 89123456,T3
t3-recepcao-2 => 91234567,T3
"""
    return static, dynamic


def test_preflight_requires_exact_mailboxes_and_distinct_strong_pins():
    assert validate_prepared_voicemail(*sample()) == {
        "ok": True, "mailboxes": 10, "invalid": 0,
    }


def test_preflight_rejects_reused_pin_between_tenants():
    static, dynamic = sample()
    dynamic = dynamic.replace("89123456", "12345679")
    assert not validate_prepared_voicemail(static, dynamic)["ok"]


def test_preflight_rejects_weak_pin_and_cross_tenant_mailbox():
    static, dynamic = sample()
    assert not validate_prepared_voicemail(static.replace("12345679", "1234"), dynamic)["ok"]
    assert not validate_prepared_voicemail(static.replace("t2-1001 =>", "t1-1001 =>"), dynamic)["ok"]


def test_preflight_rejects_confused_prefix_missing_mailbox_or_malformed_input():
    static, dynamic = sample()
    assert not validate_prepared_voicemail(static.replace("[t2]", "[t10]"), dynamic)["ok"]
    assert not validate_prepared_voicemail(static.replace("t1-1002 =>", "t1-1999 =>"), dynamic)["ok"]
    assert not validate_prepared_voicemail(static, dynamic.replace("t3-1001 =>", "t10-1001 =>"))["ok"]
    assert not validate_prepared_voicemail(static + "t2-1001 => 19234567,duplicate\n", dynamic)["ok"]
    for invalid in (None, [], "x" * (1024 * 1024 + 1)):
        assert not validate_prepared_voicemail(invalid, dynamic)["ok"]


def test_lab_prepare_uses_randomized_mailbox_pins_without_exposing_them(tmp_path):
    root = Path(__file__).resolve().parents[2]
    prepared = prepare(root, tmp_path/"staging")
    static = (prepared["conf"] / "voicemail.conf").read_text()
    dynamic = (prepared["conf"] / "voicemail_tenants"/"t3.conf").read_text()
    verified = validate_prepared_voicemail(static, dynamic)
    assert verified == {"ok": True, "mailboxes": 10, "invalid": 0}
    assert "troque_esta_senha_vm_" not in static
    assert " => 1234," not in static

def test_preflight_refuses_obvious_eight_digit_sequences():
    static, dynamic = sample()
    for weak in ("12345678", "87654321", "11223344", "12121212"):
        changed = static.replace("12345679", weak)
        assert not validate_prepared_voicemail(changed, dynamic)["ok"]


def test_voicemail_runtime_lab_endpoint_is_ephemeral_not_production(tmp_path):
    """t3-1001 is a deposit-only mailbox until prepare_calls adds a lab SIP peer."""
    assert CASES == (("t1", "t1-1001"), ("t2", "t2-1001"),
                     ("t3", "t3-1001"))
    root = Path(__file__).resolve().parents[2]
    prepared = prepare(root, tmp_path / "sip-voicemail-staging")
    assert "t3-1001" not in prepared["credentials"]
    dynamic = (prepared["conf"] / "voicemail_tenants" / "t3.conf").read_text()
    assert "[t3]" in dynamic
    assert "t3-1001 => " in dynamic
    assert "t3-recepcao => " in dynamic
    prepare_calls(root, prepared, "HEAD")
    assert all(endpoint in prepared["credentials"] for _, endpoint in CASES)
    assert "t3-1001" in (prepared["conf"] / "generated" / "pjsip_dynamic.conf").read_text()
