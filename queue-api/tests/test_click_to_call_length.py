from click_to_call import sanitize_phone_number


def test_e164_upper_limit():
    assert sanitize_phone_number("+123456789012345") == "+123456789012345"
    assert sanitize_phone_number("+1234567890123456") is None


def test_short_number_rejected():
    assert sanitize_phone_number("1234567") is None


def test_brazilian_number_unchanged():
    assert sanitize_phone_number("(11) 99999-8888") == "11999998888"
