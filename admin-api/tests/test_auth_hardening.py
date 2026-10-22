from auth import verify_password, hash_password


def test_corrupted_hex_is_rejected_without_exception():
    assert verify_password("senha", "zz" * 16 + ":" + "aa" * 32) is False
    assert verify_password("senha", "aa" * 16 + ":" + "zz" * 32) is False


def test_truncated_hash_fails_closed():
    assert verify_password("senha", "aa:bb") is False


def test_password_type_fails_closed():
    assert verify_password(None, hash_password("senha")) is False


def test_valid_hash_still_verifies():
    assert verify_password("senha-segura", hash_password("senha-segura")) is True
