from totp import generate_secret, generate_totp, verify_totp


def test_rejects_unexpected_token_types():
    secret = generate_secret()
    for code in (123456, [], None, "12345", "1234567", "１２３４５６"):
        assert verify_totp(secret, code, timestamp=60) is False


def test_rejects_invalid_time_window():
    secret = generate_secret()
    assert verify_totp(secret, "123456", timestamp=60, step=0) is False
    assert verify_totp(secret, "123456", timestamp=60, window=-1) is False


def test_valid_totp_still_passes():
    secret = generate_secret()
    code = generate_totp(secret, timestamp=60)
    assert verify_totp(secret, code, timestamp=60) is True
