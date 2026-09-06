from blocklist import validate_blocklist_number


def test_accepts_clean_number():
    assert validate_blocklist_number("08007070707") == "08007070707"


def test_cleans_formatting_characters():
    assert validate_blocklist_number("(0800) 707-0707") == "08007070707"


def test_rejects_too_short_number():
    assert validate_blocklist_number("12") is None


def test_rejects_empty_or_none():
    assert validate_blocklist_number("") is None
    assert validate_blocklist_number(None) is None


def test_rejects_non_string_input():
    assert validate_blocklist_number(12345) is None


def test_rejects_letters_mixed_in():
    assert validate_blocklist_number("liga-para-123456") == "123456"


def test_rejects_number_too_long():
    assert validate_blocklist_number("1" * 25) is None
