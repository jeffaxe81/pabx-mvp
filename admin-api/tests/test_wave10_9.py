from vip import validate_vip_input

def test_vip_rejects_oversized_raw_phone_formatting():
    data = {"number":"1"*3 + "-"*200, "target_extension":"1010"}
    assert validate_vip_input(data)[0] is False

def test_vip_accepts_formatted_phone_within_bound():
    ok, _, cleaned = validate_vip_input({"number":"(11) 99999-8888", "target_extension":"1010"})
    assert ok is True and cleaned["number"] == "11999998888"
