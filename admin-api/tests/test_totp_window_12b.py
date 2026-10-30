from totp import generate_secret, generate_totp, verify_totp

def test_totp_drift_window_bounded():
    secret = generate_secret()
    code = generate_totp(secret, timestamp=1700000000)
    assert verify_totp(secret, code, timestamp=1700000000, window=1)
    for window in (True, -1, 3, 100000):
        assert not verify_totp(secret, code, timestamp=1700000000, window=window)

def test_totp_rejects_bad_clock_and_step():
    secret = generate_secret()
    for ts in (float("inf"), float("nan"), -1, "1700000"):
        assert not verify_totp(secret, "123456", timestamp=ts)
    assert not verify_totp(secret, "123456", step=True)
