"""Retenção com WAV íntegro, expurgo opt-in, ACL do filesystem."""
import os
from pathlib import Path
import wave

from lab.recording_retention_checks import (
    inspect_retention_copy, required_retention_checks,
)


def _wav(path):
    with wave.open(str(path), "wb") as opened:
        opened.setnchannels(1)
        opened.setsampwidth(2)
        opened.setframerate(8000)
        opened.writeframes(b"\0\0" * 6000)
    path.chmod(0o600)


def test_real_wav_copy_retention_keeps_new_and_source(tmp_path):
    origin = tmp_path / "original.wav"
    _wav(origin)
    folder = tmp_path / "tenant-t1"
    folder.mkdir(mode=0o700)
    result = inspect_retention_copy(folder, origin, clock=1_793_000_000.0)
    assert len(result) == 7
    assert all(result.values())
    assert origin.exists()
    assert (folder / "recent.wav").exists()
    assert not (folder / "expired.wav").exists()
    assert (folder / "linked.wav").is_symlink()


def test_retention_checks_are_mandatory_for_t1_t2_t3():
    required = required_retention_checks()
    assert len(required) == 21
    assert "retention_expired_deleted:t1" in required
    assert "retention_source_unchanged:t3" in required
    from lab.call_checks import required_call_checks
    from lab.asterisk_lab import summarize
    base = {
        "real_runtime", "tls_transport", "wss_transport", "container_removed",
        "checkout_clean", "runtime_mounts", "source_label",
    }
    base.update(
        name + ":" + tenant for tenant in ("t1", "t2", "t3")
        for name in ("context", "register", "contact",
                     "unregister", "wrong_password")
    )
    base |= required_call_checks()
    assert summarize({key: True for key in base}, calls=True)["success"]
    incomplete = {key: True for key in base if key != "retention_expired_deleted:t1"}
    assert summarize(incomplete, calls=True)["success"] is False
