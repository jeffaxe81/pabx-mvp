from blocklist import validate_blocklist_number

def test_blocklist_refuses_oversized_raw_formatting():
    assert validate_blocklist_number("1"*3 + "-"*200) is None
    assert validate_blocklist_number("("+"1"*10+")") == "1"*10

def test_blocklist_refuses_unsafe_control_characters():
    assert validate_blocklist_number("1234\n5678") is None
