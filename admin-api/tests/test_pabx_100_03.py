"""100-test cycle 21–30: extension input contracts. No Asterisk or real credentials."""
from store import validate_extension_input

BASE={"name":"ramal-axe","number":1112,"display_name":"Ramal AXE",
      "password":"SenhaSipValida2026"}

def check(changes=None,existing=None,**kwargs):
    return validate_extension_input({**BASE,**(changes or {})},
                                    [] if existing is None else existing,**kwargs)

def test_021_new_extension_valid_and_tenant_t1():
    ok,_,data=check()
    assert ok and data["tenant"]=="t1" and data["number"]==1112

def test_022_numeric_string_normalized():
    ok,_,data=check({"number":"1112"})
    assert ok and data["number"]==1112

def test_023_boolean_extension_number_denied():
    assert not check({"number":True})[0]

def test_024_extension_number_below_range_denied():
    assert not check({"number":1099})[0]

def test_025_extension_number_above_range_denied():
    assert not check({"number":1200})[0]

def test_026_same_number_same_tenant_denied():
    assert not check(existing=[{"name":"other","number":1112,"tenant":"t1"}])[0]

def test_027_same_number_other_tenant_permitted():
    ok,_,data=check({"tenant":"t2"},
          existing=[{"name":"other","number":1112,"tenant":"t1"}])
    assert ok and data["tenant"]=="t2"

def test_028_unregistered_company_denied():
    assert not check({"tenant":"t999"})[0]

def test_029_sip_password_injection_rejected():
    for password in ("X"*12+"\nAction: Login","short","A"*20+";malicious"):
        assert not check({"password":password})[0]

def test_030_voicemail_pin_is_server_generated_only():
    assert not check({"voicemail_pin":"12345678"})[0]
    ok,_,data=check()
    assert ok and len(data["voicemail_pin"])==8 and data["voicemail_pin"].isdigit()
