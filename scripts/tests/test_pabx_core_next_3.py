"""No PIN or mailbox secret is logged, and malformed tenant rows fail closed."""
from lab.voicemail_pin_checks import validate_prepared_voicemail

def sample():
    from test_voicemail_pin_bootstrap_lab import sample as fixture
    return fixture()

def test_voicemail_preflight_accepts_nominal_generated_data():
    assert validate_prepared_voicemail(*sample())["ok"]

def test_voicemail_preflight_rejects_malformed_mailbox_entry():
    static,dynamic=sample()
    static=static.replace("t1-1001 => 12345679,T1","t1-1001 => 12345679,T1\nt1-9999 = hidden")
    report=validate_prepared_voicemail(static,dynamic)
    assert not report["ok"] and report["invalid"] >= 1
    assert "hidden" not in str(report)

def test_voicemail_preflight_detects_unparsed_mailbox_in_dynamic_tenant():
    static,dynamic=sample()
    dynamic=dynamic.replace("t3-1001 => 81235679,T3","t3-1001 => 81235679,T3\nt3-1002: malformed")
    assert not validate_prepared_voicemail(static,dynamic)["ok"]

def test_voicemail_preflight_allows_general_settings_and_include():
    static,dynamic=sample()
    static=static.replace("format=wav","format=wav\nmaxlogins=3")
    dynamic+="#include ignored_by_parser.conf\n"
    assert validate_prepared_voicemail(static,dynamic)["ok"]
