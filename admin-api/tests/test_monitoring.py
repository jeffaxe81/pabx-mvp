from monitoring import validate_monitoring_pin_input


def test_accepts_valid_pin():
    ok, error, cleaned = validate_monitoring_pin_input({"pin": "482913"})
    assert ok is True
    assert cleaned == "482913"


def test_rejects_too_short_pin():
    ok, error, _ = validate_monitoring_pin_input({"pin": "123"})
    assert ok is False


def test_rejects_too_long_pin():
    ok, error, _ = validate_monitoring_pin_input({"pin": "12345678901"})
    assert ok is False


def test_rejects_non_numeric_pin():
    ok, error, _ = validate_monitoring_pin_input({"pin": "abcd"})
    assert ok is False


def test_rejects_empty_pin():
    ok, error, _ = validate_monitoring_pin_input({})
    assert ok is False


def test_strips_whitespace():
    ok, error, cleaned = validate_monitoring_pin_input({"pin": "  4829  "})
    assert ok is True
    assert cleaned == "4829"
