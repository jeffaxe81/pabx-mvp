from users import find_user

def test_user_lookup_ignores_corrupt_rows_without_exposing_user():
    users = [None, "invalid", {"role":"admin"}, {"username":"supervisor","role":"supervisor"}]
    assert find_user(users,"supervisor")["role"] == "supervisor"
    assert find_user(users,"admin") is None
    assert find_user(None,"supervisor") is None
    assert find_user(users,[]) is None
