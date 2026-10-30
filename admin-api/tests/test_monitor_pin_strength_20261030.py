from monitoring import validate_monitoring_pin_input

def test_common_or_repeated_pins_are_denied():
    for pin in ("0000", "111111", "1234", "4321", "123456", "654321"):
        ok, _, _ = validate_monitoring_pin_input({"pin": pin})
        assert ok is False

def test_strong_pin_keeps_prior_contract():
    ok, _, pin = validate_monitoring_pin_input({"pin": "482913"})
    assert ok and pin == "482913"
