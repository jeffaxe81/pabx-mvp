from blocklist import validate_blocklist_number

def test_control_characters_are_rejected():
    for v in ("1234\n5678", "1234\r5678", "1234\x005678", "1234\t5678"):
        assert validate_blocklist_number(v) is None

def test_conventional_phone_format_is_still_allowed():
    assert validate_blocklist_number("(0800) 707-0707") == "08007070707"
