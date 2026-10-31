from totp import generate_totp, verify_totp

def test_totp_accepts_valid_and_rejects_modified_code():
    secret = "JBSWY3DPEHPK3PXP"
    value = generate_totp(secret, timestamp=120)
    assert verify_totp(secret, value, timestamp=120, window=0)
    wrong = ("0" if value[0] != "0" else "1") + value[1:]
    assert not verify_totp(secret, wrong, timestamp=120, window=0)
