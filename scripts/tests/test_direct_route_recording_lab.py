"""Contrato para quatro rotas versionadas 1010/1011 em staging privado."""
from pathlib import Path
import shutil

import pytest

from lab.call_checks import required_call_checks
from lab.direct_route_recording_checks import (
    CASES, required_direct_route_checks, original_mixmonitor_line,
    prepare_direct_route_checks, expected_wav_name, direct_cdr_reference,
)

ROOT = Path(__file__).resolve().parents[2]


def test_four_original_routes_staged_without_modifying_checkout(tmp_path):
    original = ROOT / "asterisk/extensions.conf"
    baseline = original.read_text(encoding="utf-8")
    stage = tmp_path / "asterisk"
    stage.mkdir()
    shutil.copyfile(original, stage / "extensions.conf")
    prepare_direct_route_checks({"conf": stage})
    modified = (stage / "extensions.conf").read_text(encoding="utf-8")
    assert original.read_text(encoding="utf-8") == baseline
    assert len(CASES) == 4
    for tenant, number in CASES:
        assert original_mixmonitor_line(tenant, number) in modified
        assert original_mixmonitor_line(tenant, number) in baseline
    assert modified.count("NoOp(AXE-LAB-AVISO-IGNORADO)") == 4
    assert modified.count("Dial(PJSIP/t1-1002,20,g)") >= 2
    assert modified.count("Dial(PJSIP/t2-1002,20,g)") >= 2
    assert (stage / "extensions.conf").stat().st_mode & 0o077 == 0
    with pytest.raises(ValueError, match="divergente|duplicada"):
        prepare_direct_route_checks({"conf": stage})


def test_mutated_mixmonitor_must_refuse_test_preparation(tmp_path):
    original = (ROOT / "asterisk/extensions.conf").read_text(encoding="utf-8")
    altered = original.replace(
        original_mixmonitor_line("t2", "1011"),
        " same => n,NoOp(sem-gravacao)"
    )
    assert altered != original
    stage = tmp_path / "asterisk"
    stage.mkdir()
    path = stage / "extensions.conf"
    path.write_text(altered, encoding="utf-8")
    with pytest.raises(ValueError, match="divergente"):
        prepare_direct_route_checks({"conf": stage})
    assert path.read_text(encoding="utf-8") == altered


def test_direct_route_checks_are_required_and_names_are_exact():
    required = required_direct_route_checks()
    assert len(required) == len(CASES) * 9 == 36
    assert required <= required_call_checks()
    assert expected_wav_name("20261029-130001-1001-1010.wav", "t1", "1010")
    assert expected_wav_name("20261029-130001-1001-t2-1011.wav", "t2", "1011")
    for filename, tenant, number in (
        ("20261029-130001-1001-t2-1010.wav", "t1", "1010"),
        ("20261029-130001-1001-1010.wav", "t2", "1010"),
        ("20261029-130001-1001-t10-1010.wav", "t1", "1010"),
        ("20261029-130001-1001-t2-1011.wav", "t2", "1010"),
        ("../../../foo.wav", "t1", "1011"),
    ):
        assert not expected_wav_name(filename, tenant, number)


@pytest.mark.parametrize("tenant,number", CASES)
def test_cdr_requires_same_tenant_origin_destination_answer(tenant, number):
    row = (f"{tenant},1001,{number},{tenant}-internal,"
           f"PJSIP/{tenant}-1001-0000000a,PJSIP/{tenant}-1002-0000000b,"
           "ANSWERED,2,1792670400.123\n")
    assert direct_cdr_reference(row, tenant, number) == "CDR:1792670400.123"
    assert direct_cdr_reference(row + row, tenant, number) is None
    assert direct_cdr_reference(row, "t10", number) is None
    for bad in (
        row.replace("ANSWERED", "NO ANSWER"),
        row.replace(f"{tenant}-internal", "t10-internal"),
        row.replace(f"PJSIP/{tenant}-1002", "PJSIP/t10-1002"),
        row.replace(f"PJSIP/{tenant}-1001", "PJSIP/t10-1001"),
        row.replace(f",{number},", ",1000,"),
    ):
        assert direct_cdr_reference(bad, tenant, number) is None


def test_restoration_preserves_original_webrtc_destinations(tmp_path, monkeypatch):
    from lab.direct_route_recording_checks import restore_direct_route_checks
    stage = tmp_path / "asterisk"
    stage.mkdir()
    path = stage / "extensions.conf"
    baseline = (ROOT / "asterisk/extensions.conf").read_text(encoding="utf-8")
    path.write_text(baseline, encoding="utf-8")
    prepared = {"conf": stage}
    prepare_direct_route_checks(prepared)
    assert prepared["lab_direct_route_staged"]
    seen = []

    def fake_cli(container, cmd):
        assert container == "test-container"
        seen.append(cmd)
        if cmd == "dialplan reload":
            return "Dialplan reloaded."
        if cmd.startswith("dialplan show "):
            dial = cmd.partition("dialplan show ")[2]
            number, _, ctx = dial.partition("@")
            tenant = ctx.split("-internal")[0]
            if tenant not in {"t1", "t2"} or number not in {"1010", "1011"}:
                return ""
            target = tenant + ("-recepcao" if number == "1010" else "-recepcao-2")
            return ("MixMonitor(/var/spool/asterisk/monitor/file.wav,b)\n"
                    + f"Dial(PJSIP/{target},20,g)\n")
        return ""

    monkeypatch.setattr("lab.asterisk_lab.cli", fake_cli)
    restore_direct_route_checks("test-container", prepared)
    assert path.read_text(encoding="utf-8") == baseline
    assert prepared["lab_direct_route_restored"] is True
    assert prepared["lab_direct_route_staged"] is False
    assert len(seen) == 5
    with pytest.raises(ValueError, match="ausente"):
        restore_direct_route_checks("test-container", prepared)


def test_restore_rejects_missing_webrtc_destination(tmp_path, monkeypatch):
    from lab.direct_route_recording_checks import restore_direct_route_checks
    stage = tmp_path / "asterisk"
    stage.mkdir()
    path = stage / "extensions.conf"
    baseline = (ROOT / "asterisk/extensions.conf").read_text(encoding="utf-8")
    path.write_text(baseline, encoding="utf-8")
    prepared = {"conf": stage}
    prepare_direct_route_checks(prepared)
    monkeypatch.setattr("lab.asterisk_lab.cli", lambda *_: "Dialplan reloaded.")
    with pytest.raises(ValueError, match="não foi restaurada"):
        restore_direct_route_checks("test-container", prepared)
