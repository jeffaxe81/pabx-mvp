import pytest
from totp import generate_secret

def test_totp_secret_generation_is_bounded():
    for invalid in (0, -1, 9, 65, 1000000, True, None, "20"):
        with pytest.raises(ValueError):
            generate_secret(invalid)
    assert isinstance(generate_secret(20), str)
    assert len(generate_secret(20)) >= 32
