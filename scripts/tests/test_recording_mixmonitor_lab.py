"""Regressões de aceitação MixMonitor em Asterisk descartável (sem cliente)."""
from pathlib import Path

import pytest

from lab.call_checks import required_call_checks
from lab.recording_checks import (
    TENANTS, MIN_AUDIO_BYTES, prepare_recording_routes,
    recording_cdr_matches, recording_size_valid, required_recording_checks,
)


def test_lab_mixmonitor_routes_exist_only_in_private_staging(tmp_path):
    root = tmp_path / "staging"
    root.mkdir()
    baseline = "[t1-internal]\nexten => 1000,1,Answer()\n"
    (root / "extensions.conf").write_text(baseline)
    prepared = {"conf": root}
    prepare_recording_routes(prepared)
    staged = (root / "extensions.conf").read_text()
    assert staged.startswith(baseline.rstrip())
    assert staged.count("AXE-LAB-MIXMONITOR-ONLY") == 1
    assert staged.count("exten => 9988,1,Answer()") == 3
    assert staged.count("StopMixMonitor()") == 3
    assert staged.count("Set(CDR(accountcode)=") == 3
    assert set(prepared["lab_recording_filenames"]) == set(TENANTS)
    assert len(set(prepared["lab_recording_filenames"].values())) == 3
    for tenant, filename in prepared["lab_recording_filenames"].items():
        assert f"[{tenant}-internal](+)" in staged
        assert f"/monitor/{tenant}/{filename}" in staged
    assert (root / "extensions.conf").stat().st_mode & 0o077 == 0
    with pytest.raises(ValueError, match="duplicadas"):
        prepare_recording_routes(prepared)


def test_lab_mixmonitor_checklist_is_mandatory_with_live_call_suite():
    expected = required_recording_checks()
    assert len(expected) == 27
    assert expected <= required_call_checks()
    assert "lab_recording_file:t3" in expected
    assert "lab_recording_no_foreign_file:t1" in expected


@pytest.mark.parametrize("tenant", TENANTS)
def test_lab_cdr_must_correlate_tenant_and_unique_call(tenant):
    sample = f"{tenant},1001,9988,{tenant}-internal,PJSIP/{tenant}-1001-0000000a,,ANSWERED,2,1792670400.123\n"
    assert recording_cdr_matches(sample, tenant)
    assert not recording_cdr_matches(sample, next(x for x in TENANTS if x != tenant))
    assert not recording_cdr_matches(sample.replace("ANSWERED", "NO ANSWER"), tenant)
    assert not recording_cdr_matches(sample.replace("9988", "1000"), tenant)
    assert not recording_cdr_matches(sample + sample, tenant)
    assert not recording_cdr_matches(sample.replace(f"{tenant}-internal", "t10-internal"), tenant)
    assert not recording_cdr_matches(sample.replace("PJSIP/", "Local/"), tenant)


def test_lab_recording_size_needs_audio_data_not_only_wav_header():
    for invalid in ("", "RIFF", "0", "44", "-2000", "9999999999999", None, [], 1):
        assert not recording_size_valid(invalid)
    assert recording_size_valid(str(MIN_AUDIO_BYTES))
    assert recording_size_valid("40960\n")
