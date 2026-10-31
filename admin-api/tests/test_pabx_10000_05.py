"""1.000 instantes TOTP únicos: janela temporal e códigos Unicode maliciosos."""
import pytest
from totp import generate_totp,verify_totp

SECRET="JBSWY3DPEHPK3PXP"

@pytest.mark.parametrize("case", [
    pytest.param(i,id=f"AXE-{i+4001:05d}") for i in range(1000)
])
def test_totp_1000_unique_timestamps_and_code_formats(case):
    timestamp=600+case*30
    valid=generate_totp(SECRET,timestamp=timestamp)
    if case<500:
        # Exatamente um período aceito; instante da mesma janela.
        assert valid.isascii() and len(valid)==6
        assert verify_totp(SECRET,valid,timestamp=timestamp+29,window=0)
    else:
        # Códigos de seis caracteres, mas um dígito é Unicode não ASCII.
        index=case%6
        spoofed=valid[:index]+"９"+valid[index+1:]
        assert len(spoofed)==6
        assert not verify_totp(SECRET,spoofed,timestamp=timestamp,window=0)
