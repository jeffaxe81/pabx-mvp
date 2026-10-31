"""AXE PABX puro: 1.000 instantes distintos e códigos de segundo fator."""
import pytest
from totp import generate_totp,verify_totp

SECRET="JBSWY3DPEHPK3PXP"

@pytest.mark.parametrize("case",[pytest.param(i,id=f"AXE-{i+4001:05d}") for i in range(1000)])
def test_totp_at_1000_distinct_time_windows(case):
    timestamp=600+case*30
    code=generate_totp(SECRET,timestamp=timestamp)
    if case<500:
        assert code.isascii() and len(code)==6 and code.isdecimal()
        assert verify_totp(SECRET,code,timestamp=timestamp+29,window=0)
    else:
        location=case%6
        spoofed=code[:location]+"９"+code[location+1:]
        assert len(spoofed)==6
        assert not verify_totp(SECRET,spoofed,timestamp=timestamp,window=0)
