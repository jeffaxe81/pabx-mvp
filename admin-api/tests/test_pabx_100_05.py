"""100-test cycle 41–50: telephone number sanitation and routing policy."""
from blocklist import validate_blocklist_number
from vip import validate_vip_input

def vip(number="(11) 9999-8888",target="1001"):
    return validate_vip_input({"number":number,"target_extension":target})

def test_041_blocklist_accepts_national_number():
    assert validate_blocklist_number("(11) 9999-8888")=="1199998888"

def test_042_blocklist_accepts_international_plus_prefix():
    assert validate_blocklist_number("+55 11 9999-8888")=="551199998888"

def test_043_blocklist_rejects_short_number():
    assert validate_blocklist_number("12") is None

def test_044_blocklist_rejects_long_number():
    assert validate_blocklist_number("9"*21) is None

def test_045_blocklist_rejects_control_code():
    for value in ("11999\n98888","11999\r98888","11999\x0098888"):
        assert validate_blocklist_number(value) is None

def test_046_blocklist_rejects_invisible_unicode():
    for value in ("11\u200b99998888","11\u202e99998888"):
        assert validate_blocklist_number(value) is None

def test_047_vip_routes_formatted_number_to_extension():
    ok,_,row=vip()
    assert ok and row=={"number":"1199998888","target_extension":"1001"}

def test_048_vip_rejects_non_numeric_extension():
    assert not vip(target="1001;Dial(PJSIP/secret)")[0]

def test_049_vip_rejects_short_extension():
    assert not vip(target="12")[0]

def test_050_vip_rejects_hidden_unicode_in_caller_id():
    assert not vip(number="1199\u200b998888")[0]
