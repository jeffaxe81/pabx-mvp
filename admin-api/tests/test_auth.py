from auth import hash_password, verify_password, SessionStore


def test_verify_correct_password():
    stored = hash_password("minha-senha-123")
    assert verify_password("minha-senha-123", stored) is True


def test_verify_rejects_wrong_password():
    stored = hash_password("minha-senha-123")
    assert verify_password("senha-errada", stored) is False


def test_same_password_generates_different_hashes_due_to_salt():
    """Sem isso, dois admins com a mesma senha teriam o mesmo hash - vazamento de informação."""
    hash1 = hash_password("123456")
    hash2 = hash_password("123456")
    assert hash1 != hash2
    assert verify_password("123456", hash1)
    assert verify_password("123456", hash2)


def test_verify_rejects_malformed_stored_hash():
    assert verify_password("qualquer", "isso-nao-e-um-hash-valido") is False
    assert verify_password("qualquer", "") is False
    assert verify_password("qualquer", None) is False


def test_session_create_and_validate():
    store = SessionStore()
    token = store.create("admin")
    assert store.validate(token) == "admin"


def test_session_validate_rejects_unknown_token():
    store = SessionStore()
    assert store.validate("token-que-nao-existe") is None


def test_session_expires_after_ttl():
    clock_value = [1000.0]
    store = SessionStore(ttl_seconds=60, clock=lambda: clock_value[0])
    token = store.create("admin")

    assert store.validate(token) == "admin"

    clock_value[0] += 61
    assert store.validate(token) is None


def test_session_revoke_invalidates_token():
    store = SessionStore()
    token = store.create("admin")
    store.revoke(token)
    assert store.validate(token) is None


def test_tokens_are_unique_and_unpredictable():
    store = SessionStore()
    tokens = {store.create("admin") for _ in range(20)}
    assert len(tokens) == 20
    assert all(len(t) >= 32 for t in tokens)
