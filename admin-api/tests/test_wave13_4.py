from blocklist import validate_blocklist_number

def test_blocklist_rejects_unicode_control_characters():
    for value in ("11999\u200b98888", "11999\u202e98888", "11999\u206098888"):
        assert validate_blocklist_number(value) is None
    assert validate_blocklist_number("(11) 9999-8888") == "1199998888"
