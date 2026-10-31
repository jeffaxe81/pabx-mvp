"""100-test cycle 31–40: PBX administrator and supervisor safety."""
from users import (add_user,delete_user,find_user,load_users,
                   public_user,update_user,validate_user_input)
from auth import verify_password

VALID={"username":"adminaxe","role":"admin","password":"PABXadmin-2026!"}

def test_031_user_creation_persists_hashed_password(tmp_path):
    path=tmp_path/"users.json"
    ok,_,user=add_user(path,VALID)
    assert ok and verify_password(VALID["password"],user["password_hash"])
    assert load_users(path)[0]["username"]=="adminaxe"

def test_032_supervisor_role_is_accepted():
    ok,_,data=validate_user_input({**VALID,"role":"supervisor"},[])
    assert ok and data["role"]=="supervisor"

def test_033_role_escalation_to_unrecognized_role_denied():
    assert not validate_user_input({**VALID,"role":"root"},[])[0]

def test_034_username_case_and_spaces_are_normalized():
    ok,_,data=validate_user_input({**VALID,"username":" ADMINAXE "},[])
    assert ok and data["username"]=="adminaxe"

def test_035_short_username_denied():
    assert not validate_user_input({**VALID,"username":"ab"},[])[0]

def test_036_username_with_conf_delimiter_denied():
    assert not validate_user_input({**VALID,"username":"admin;evil"},[])[0]

def test_037_duplicate_admin_username_denied():
    existing=[{"username":"adminaxe","role":"admin","password_hash":"HASH"}]
    assert not validate_user_input(VALID,existing)[0]

def test_038_lookup_ignores_malformed_records():
    rows=[None,"bad",{},{"username":"adminaxe","role":"admin"}]
    assert find_user(rows,"adminaxe")["role"]=="admin"
    assert find_user(rows,"missing") is None

def test_039_public_user_never_exposes_password_or_totp():
    public=public_user({"username":"adminaxe","role":"admin",
         "password_hash":"secret-hash","totp_secret":"totp-secret","totp_enabled":True})
    assert "password_hash" not in public and "totp_secret" not in public
    assert public["totp_enabled"] is True

def test_040_last_admin_cannot_be_deleted(tmp_path):
    path=tmp_path/"users.json"
    assert add_user(path,VALID)[0]
    ok,_=delete_user(path,"adminaxe")
    assert not ok and len(load_users(path))==1
