from vip import validate_vip_input

def test_vip_rejects_hidden_controls():
    for number in ("1199999\n8888", "1199999\r8888", "1199999\t8888", "1199999\x008888"):
        ok, _, clean = validate_vip_input({"number": number, "target_extension": "1010"})
        assert not ok and clean is None

def test_vip_formatted_number_works():
    ok, _, data = validate_vip_input({"number": "(11) 99999-8888", "target_extension": "1010"})
    assert ok and data["number"] == "11999998888"
