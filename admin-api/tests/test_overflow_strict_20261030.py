from overflow import validate_overflow_timeout_input

def test_bad_input_shapes_rejected():
    for data in (None, [], "30", {"seconds": True}, {"seconds": 30.9}, {"seconds": "3e1"}, {"seconds": " 30 "}):
        assert validate_overflow_timeout_input(data)[0] is False

def test_integer_or_numeric_ascii_string_accepted():
    assert validate_overflow_timeout_input({"seconds": 30})[0] is True
    assert validate_overflow_timeout_input({"seconds": "30"})[0] is True
