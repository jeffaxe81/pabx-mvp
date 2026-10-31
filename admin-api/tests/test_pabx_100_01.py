"""100-test cycle 01–10: PABX management TOTP contract. Unit tests only."""
import base64
import math
import urllib.parse
import pytest
from totp import generate_secret, generate_totp, verify_totp, build_provisioning_uri

SECRET="JBSWY3DPEHPK3PXP"
AT=900

def test_001_valid_six_digit_totp():
    token=generate_totp(SECRET,timestamp=AT)
    assert len(token)==6 and token.isascii() and token.isdecimal()
    assert verify_totp(SECRET,token,timestamp=AT,window=0)

def test_002_totp_remains_valid_inside_step():
    token=generate_totp(SECRET,timestamp=900)
    assert verify_totp(SECRET,token,timestamp=929,window=0)

def test_003_totp_adjacent_window_accepts_clock_drift():
    token=generate_totp(SECRET,timestamp=900)
    assert verify_totp(SECRET,token,timestamp=930,window=1)

def test_004_totp_rejects_expired_token_with_zero_window():
    token=generate_totp(SECRET,timestamp=900)
    assert not verify_totp(SECRET,token,timestamp=930,window=0)

def test_005_totp_rejects_ascii_nondigits():
    for token in ("ABCDEF","12345x","12 456"):
        assert not verify_totp(SECRET,token,timestamp=AT)

def test_006_totp_rejects_unicode_digit_spoofing():
    for token in ("１２３４５６","١٢٣٤٥٦","１２3４５6"):
        assert not verify_totp(SECRET,token,timestamp=AT)

def test_007_totp_rejects_nonfinite_time():
    token=generate_totp(SECRET,timestamp=AT)
    for time in (float("nan"),float("inf"),float("-inf"),-1):
        assert not verify_totp(SECRET,token,timestamp=time)

def test_008_totp_rejects_invalid_window_and_step():
    token=generate_totp(SECRET,timestamp=AT)
    for window in (-1,3,True,"1"):
        assert not verify_totp(SECRET,token,timestamp=AT,window=window)
    for step in (0,-1,True,"30"):
        assert not verify_totp(SECRET,token,timestamp=AT,step=step)

def test_009_totp_secret_generation_bounds_and_randomness():
    values={generate_secret() for _ in range(4)}
    assert len(values)==4 and all(len(base64.b32decode(s+"="*((-len(s))%8)))==20 for s in values)
    for length in (0,9,65,True,20.0):
        with pytest.raises(ValueError):
            generate_secret(length)

def test_010_totp_provisioning_uri_encodes_identity():
    uri=build_provisioning_uri(SECRET,"admin+sip@corp","AXE PABX")
    parsed=urllib.parse.urlparse(uri)
    query=urllib.parse.parse_qs(parsed.query)
    assert parsed.scheme=="otpauth" and parsed.netloc=="totp"
    assert urllib.parse.unquote(parsed.path)=="/AXE PABX:admin+sip@corp"
    assert query["secret"]==[SECRET] and query["issuer"]==["AXE PABX"]
    assert query["digits"]==["6"] and query["period"]==["30"]
