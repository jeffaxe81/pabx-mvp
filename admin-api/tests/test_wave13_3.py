from vip import validate_vip_input

def test_vip_rejects_unicode_format_controls_before_sanitizing():
    for raw in ("11\u200b99998888", "11\u202e99998888", "11\u206099998888"):
        ok, _, item = validate_vip_input({"number":raw,"target_extension":"1001"})
        assert not ok and item is None
    ok, _, item = validate_vip_input({"number":"(11) 9999-8888","target_extension":"1001"})
    assert ok and item["number"] == "1199998888"
