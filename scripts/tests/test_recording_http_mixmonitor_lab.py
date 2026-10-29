"""O replay HTTP de um WAV real deve ser prova obrigatória, nunca simulação."""
import hashlib
import json
import os
import stat
import struct

from lab.call_checks import required_call_checks
from lab.recording_http_checks import (
    TENANTS, TEST_TENANTS, _credential, _write_private_policy,
    _read_lab_wav, required_recording_http_checks, MIN_AUDIO_BYTES,
)
from lab.recording_checks import recording_cdr_reference


def test_http_proof_is_required_for_every_real_asterisk_call_suite():
    keys = required_recording_http_checks()
    assert len(keys) == 17
    assert keys <= required_call_checks()
    for tenant in TENANTS:
        assert f"rec_http_list:{tenant}" in keys
        assert f"rec_http_bytes:{tenant}" in keys
        assert f"rec_http_cross_denied:{tenant}" in keys
        assert f"rec_http_origin_denied:{tenant}" in keys
    assert TEST_TENANTS == ("t1", "t2", "t3", "t10")
    assert {"rec_http_revoked_t1", "rec_http_prefix_t10_denied",
            "rec_http_other_tenants_unaffected", "rec_http_verified_cdr_sources"} <= keys


def test_http_policy_uses_only_hash_and_expires(tmp_path):
    token = "V" * 48
    data = {"credentials": [_credential(token, "t1")], "recordings": {}}
    path = tmp_path / "policy.json"
    _write_private_policy(path, data, create=True)
    raw = path.read_text()
    assert token not in raw
    assert hashlib.sha256(token.encode()).hexdigest() in raw
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    parsed = json.loads(raw)
    assert parsed["credentials"][0]["role"] == "supervisor"
    assert parsed["credentials"][0]["expires_at"] > 0
    parsed["credentials"] = []
    _write_private_policy(path, parsed)
    assert json.loads(path.read_text())["credentials"] == []


def test_http_wav_validator_rejects_header_only_and_symlinks(tmp_path):
    import pytest
    valid = tmp_path / "audio.wav"
    payload = b"RIFF" + struct.pack("<I", MIN_AUDIO_BYTES - 8) + b"WAVE"
    payload += b"\x00" * (MIN_AUDIO_BYTES - len(payload))
    valid.write_bytes(payload)
    valid.chmod(0o600)
    assert _read_lab_wav(valid) == payload
    valid.write_bytes(b"RIFF" + b"x" * (MIN_AUDIO_BYTES - 4))
    with pytest.raises(ValueError, match="WAV"):
        _read_lab_wav(valid)
    valid.write_bytes(payload)
    link = tmp_path / "link.wav"
    link.symlink_to(valid)
    with pytest.raises(ValueError):
        _read_lab_wav(link)
    valid.chmod(0o644)
    with pytest.raises(ValueError, match="permissão"):
        _read_lab_wav(valid)


def test_cdr_reference_requires_one_verified_source_and_exact_tenant():
    sample = ("t1,1001,9988,t1-internal,PJSIP/t1-1001-0000000a,,"
              "ANSWERED,2,1792670400.123\n")
    assert recording_cdr_reference(sample, "t1") == "CDR:1792670400.123"
    assert recording_cdr_reference(sample, "t10") is None
    assert recording_cdr_reference(sample, "t2") is None
    assert recording_cdr_reference(sample + sample, "t1") is None
    assert recording_cdr_reference(sample.replace("ANSWERED", "BUSY"), "t1") is None
