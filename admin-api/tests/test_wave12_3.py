from monitoring import validate_monitoring_pin_input

def test_monitoring_pin_blocks_extended_sequential_patterns():
    for pin in ("0123", "2345", "345678", "9876", "87654", "9876543210"):
        ok, _, clean = validate_monitoring_pin_input({"pin":pin})
        assert not ok and clean is None
    assert validate_monitoring_pin_input({"pin":"5839"})[0] is True
