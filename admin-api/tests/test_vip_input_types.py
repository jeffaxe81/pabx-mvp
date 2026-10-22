from vip import validate_vip_input


def test_non_dict_request_rejected():
    assert validate_vip_input(None)[0] is False


def test_numeric_number_rejected_without_exception():
    assert validate_vip_input({"number": 11999998888, "target_extension": "1001"})[0] is False


def test_numeric_extension_rejected_without_exception():
    assert validate_vip_input({"number": "11999998888", "target_extension": 1001})[0] is False


def test_valid_vip_remains_valid():
    ok, _, cleaned = validate_vip_input({"number": "(11)99999-8888", "target_extension": "1001"})
    assert ok and cleaned == {"number": "11999998888", "target_extension": "1001"}
