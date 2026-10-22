from monitoring import validate_monitoring_pin_input


def test_bad_payload_type_fails_closed():
    for payload in (None, [], "1234", {"pin": 1234}, {"pin": []}):
        assert validate_monitoring_pin_input(payload)[0] is False


def test_valid_monitoring_pin():
    assert validate_monitoring_pin_input({"pin": " 987654 "}) == (True, None, "987654")
