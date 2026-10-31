from users import validate_user_input

def test_admin_user_form_rejects_invalid_payload_types():
    for bad in (None, [], False, 100, "admin"):
        ok, _, clean = validate_user_input(bad, [])
        assert not ok and clean is None
    for bad in ([], {}, 100, True, None):
        ok, _, clean = validate_user_input({"username":bad, "role":"admin","password":"secret"},[])
        assert not ok and clean is None
    assert not validate_user_input({"username":"admin","role":"admin","password":"secret"},None)[0]
