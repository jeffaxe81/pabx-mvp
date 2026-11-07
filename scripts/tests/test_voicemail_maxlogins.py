"""Configuração do limite de tentativas do VoiceMailMain é fail-closed."""
from pathlib import Path
import pytest

from lab.voicemail_pin_checks import validate_voicemail_login_limit


@pytest.mark.parametrize("maxlogins", ["1", "2", "3"])
def test_voicemail_login_limit_rejects_unrestricted_attempts(maxlogins):
    source = "[general]\nformat=wav\nmaxlogins=" + maxlogins + "\n[t1]\n"
    assert validate_voicemail_login_limit(source)


@pytest.mark.parametrize("bad", [
    "[general]\n",
    "[general]\nmaxlogins=0\n",
    "[general]\nmaxlogins=4\n",
    "[general]\nmaxlogins=999\n",
    "[general]\nmaxlogins=NaN\n",
    "[general]\nmaxlogins=3\nmaxlogins=2\n",
    "[general]\nmaxlogins=3\n[t1]\nmaxlogins=3\n",
    "[t1]\nmaxlogins=3\n",
    "[general]\nmaxlogins=3 ; injected\n",
    "[general]\nmaxlogins=03\n",
    "maxlogins=3\n[general]\n",
])
def test_bad_voicemail_limit_fails_closed(bad):
    assert not validate_voicemail_login_limit(bad)


def test_versioned_staging_template_requires_bounded_login_attempts():
    path = Path(__file__).resolve().parents[2] / "asterisk/voicemail.conf"
    assert validate_voicemail_login_limit(path.read_text(encoding="utf-8"))
    assert not validate_voicemail_login_limit(None)
    assert not validate_voicemail_login_limit("x" * (1024 * 1024 + 1))
