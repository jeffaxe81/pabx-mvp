from overflow import validate_overflow_timeout_input

def test_overflow_timeout_rejects_ambiguous_leading_zeroes():
    for raw in ("005","0005","0600","00"):
        assert validate_overflow_timeout_input({"seconds":raw})[0] is False
    for raw in ("5","60","600"):
        ok,_,seconds=validate_overflow_timeout_input({"seconds":raw})
        assert ok and seconds==int(raw)
