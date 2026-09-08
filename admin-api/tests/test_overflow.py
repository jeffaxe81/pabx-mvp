from overflow import validate_overflow_timeout_input, MIN_SECONDS, MAX_SECONDS


def test_accepts_valid_value():
    ok, error, cleaned = validate_overflow_timeout_input({"seconds": 30})
    assert ok is True
    assert cleaned == 30


def test_accepts_value_as_string():
    ok, error, cleaned = validate_overflow_timeout_input({"seconds": "45"})
    assert ok is True
    assert cleaned == 45


def test_accepts_boundary_values():
    ok_min, _, cleaned_min = validate_overflow_timeout_input({"seconds": MIN_SECONDS})
    ok_max, _, cleaned_max = validate_overflow_timeout_input({"seconds": MAX_SECONDS})
    assert ok_min is True and cleaned_min == MIN_SECONDS
    assert ok_max is True and cleaned_max == MAX_SECONDS


def test_rejects_below_minimum():
    ok, error, _ = validate_overflow_timeout_input({"seconds": MIN_SECONDS - 1})
    assert ok is False


def test_rejects_above_maximum():
    ok, error, _ = validate_overflow_timeout_input({"seconds": MAX_SECONDS + 1})
    assert ok is False


def test_rejects_non_numeric_value():
    ok, error, _ = validate_overflow_timeout_input({"seconds": "abc"})
    assert ok is False


def test_rejects_missing_value():
    ok, error, _ = validate_overflow_timeout_input({})
    assert ok is False


def test_rejects_float_string_gracefully():
    """'30.5' não é um int válido - deveria ser recusado, não truncado silenciosamente."""
    ok, error, _ = validate_overflow_timeout_input({"seconds": "30.5"})
    assert ok is False
