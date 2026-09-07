from vip import validate_vip_input

VALID_INPUT = {"number": "(11) 99999-8888", "target_extension": "1010"}


def test_accepts_correct_input_and_sanitizes_number():
    ok, error, cleaned = validate_vip_input(VALID_INPUT)
    assert ok is True
    assert cleaned["number"] == "11999998888"
    assert cleaned["target_extension"] == "1010"


def test_rejects_invalid_number():
    ok, error, _ = validate_vip_input({**VALID_INPUT, "number": "12"})
    assert ok is False
    assert "número" in error


def test_rejects_missing_target_extension():
    ok, error, _ = validate_vip_input({**VALID_INPUT, "target_extension": ""})
    assert ok is False
    assert "ramal" in error


def test_rejects_non_numeric_target_extension():
    ok, error, _ = validate_vip_input({**VALID_INPUT, "target_extension": "t1-recepcao"})
    assert ok is False
    assert "ramal" in error


def test_rejects_letters_mixed_in_number():
    ok, error, cleaned = validate_vip_input({**VALID_INPUT, "number": "liga-11999998888"})
    assert ok is True
    assert cleaned["number"] == "11999998888"
