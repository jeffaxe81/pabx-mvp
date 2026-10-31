"""100-test cycle 11–20: PABX admin security, simulated clocks only."""
from auth import SessionStore, hash_password, verify_password

def test_011_correct_password_verifies():
    hashed=hash_password("AXE-admin-2026!")
    assert verify_password("AXE-admin-2026!",hashed)

def test_012_wrong_password_denied():
    hashed=hash_password("AXE-admin-2026!")
    assert not verify_password("AXE-admin-2027!",hashed)

def test_013_corrupted_password_hash_rejected():
    for stored in ("","invalid","00:ff","x"*96,None,123):
        assert not verify_password("password",stored)

def test_014_session_token_is_random_hex():
    store=SessionStore()
    a,b=store.create("owner"),store.create("owner")
    assert a!=b and len(a)==64 and len(b)==64
    assert all(c in "0123456789abcdef" for c in a+b)

def test_015_expiry_at_exact_clock_boundary():
    time=[100.0]
    store=SessionStore(ttl_seconds=60,clock=lambda:time[0])
    token=store.create("owner")
    time[0]=159.999
    assert store.validate(token)=="owner"
    time[0]=160.0
    assert store.validate(token) is None

def test_016_revocation_blocks_replay():
    store=SessionStore()
    token=store.create("owner")
    store.revoke(token)
    assert store.validate(token) is None

def test_017_malformed_token_denied():
    store=SessionStore()
    store.create("owner")
    for token in (None,[],{},7,True,("a",)):
        assert store.validate(token) is None

def test_018_role_is_preserved_per_session():
    store=SessionStore()
    a=store.create("owner","admin")
    b=store.create("viewer","supervisor")
    assert store.get_role(a)=="admin"
    assert store.get_role(b)=="supervisor"

def test_019_expired_role_cannot_be_read():
    clock=[0]
    store=SessionStore(ttl_seconds=1,clock=lambda:clock[0])
    token=store.create("owner")
    clock[0]=1
    assert store.get_role(token) is None

def test_020_unknown_token_revoke_keeps_valid_session():
    store=SessionStore()
    real=store.create("owner")
    store.revoke("not-a-valid-token")
    assert store.validate(real)=="owner"
