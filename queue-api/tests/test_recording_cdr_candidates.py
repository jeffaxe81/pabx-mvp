import json
import os

import pytest

from recording_cdr_candidates import (
    corroborate_cdr, load_raw_cdr, propose_candidates, main,
)

FILE = "20261022-120000-551199998888-1010.wav"


def cdr(tenant="t1", **overrides):
    data = {
        "Event": "Cdr", "Disposition": "ANSWERED",
        "AccountCode": tenant, "DestinationContext": tenant + "-internal",
        "DestinationChannel": f"PJSIP/{tenant}-recepcao-00000001",
        "UniqueID": "1792670400.123",
        "CallerIDNum": "551199998888", "Destination": "1010",
        "StartTime": "2026-10-22 12:00:00",
    }
    data.update(overrides)
    return data


def file(tmp_path, name=FILE):
    recordings = tmp_path / "recordings"
    recordings.mkdir()
    (recordings / name).write_bytes(b"RIFF fake audio")
    return recordings


def test_three_cdr_fields_plus_filename_are_required(tmp_path):
    recordings = file(tmp_path)
    output, summary = propose_candidates(recordings, [cdr()])
    assert summary["proposed"] == 1
    assert output == [{
        "filename": FILE, "tenant": "t1", "source_ref": "CDR:1792670400.123",
        "owner_extension": "t1-recepcao",
    }]


@pytest.mark.parametrize("change", [
    {"AccountCode": ""},
    {"AccountCode": "t2"},
    {"DestinationContext": "t2-internal"},
    {"DestinationChannel": "PJSIP/t2-recepcao-00000002"},
    {"DestinationChannel": "PJSIP/unknown-00000002"},
    {"Event": "Hangup"},
    {"Disposition": "NO ANSWER"},
    {"UniqueID": "unexpected/../id"},
    {"CallerIDNum": "551199998887"},
    {"Destination": "1011"},
    {"StartTime": "2026-10-22 12:00:01"},
])
def test_incomplete_or_contradictory_cdr_never_proposes(tmp_path, change):
    recordings = file(tmp_path)
    output, summary = propose_candidates(recordings, [cdr(**change)])
    assert output == []
    assert summary["proposed"] == 0


def test_multiple_cdr_legs_are_ambiguous_even_same_tenant(tmp_path):
    recordings = file(tmp_path)
    output, summary = propose_candidates(recordings, [
        cdr(), cdr(UniqueID="1792670400.124"),
    ])
    assert output == []
    assert summary["ambiguous"] == 1


def test_cross_tenant_dispute_is_ambiguous(tmp_path):
    recordings = file(tmp_path)
    output, summary = propose_candidates(recordings, [
        cdr(), cdr("t2", UniqueID="1792670400.124"),
    ])
    assert output == []
    assert summary["ambiguous"] == 1


def test_explicit_tenant_in_filename_must_agree(tmp_path):
    recordings = file(tmp_path, "20261022-120000-551199998888-t2-1010.wav")
    rows, summary = propose_candidates(recordings, [cdr()])
    assert rows == []
    assert summary["without_evidence"] == 1


def test_tagged_filename_accepted_when_all_sources_agree(tmp_path):
    recordings = file(tmp_path, "20261022-120000-551199998888-t2-1010.wav")
    rows, summary = propose_candidates(recordings, [cdr("t2")])
    assert len(rows) == 1
    assert rows[0]["tenant"] == "t2"


def test_bogus_filename_and_symlinks_are_skipped(tmp_path):
    recordings = file(tmp_path)
    (recordings / "other.wav").write_bytes(b"OTHER")
    (recordings / "fake.wav").symlink_to(tmp_path / "outside.wav")
    rows, summary = propose_candidates(recordings, [cdr()])
    assert len(rows) == 1
    assert summary["unsupported"] == 2


def test_cdr_loader_rejects_symlinks_bad_json_and_oversize(tmp_path):
    path = tmp_path / "cdr.jsonl"
    path.write_text("{not json")
    with pytest.raises(ValueError, match="JSON"):
        load_raw_cdr(path)
    path.write_text(json.dumps(cdr()) + "\n")
    assert load_raw_cdr(path)[0]["AccountCode"] == "t1"
    alias = tmp_path / "alias.jsonl"
    alias.symlink_to(path)
    with pytest.raises(ValueError, match="regular"):
        load_raw_cdr(alias)
    path.write_bytes(b"a" * (4 * 1024 * 1024 + 1))
    with pytest.raises(ValueError):
        load_raw_cdr(path)


def test_cli_creates_private_manifest_without_mutating_catalog(tmp_path):
    recordings = file(tmp_path)
    source = tmp_path / "cdr.jsonl"
    source.write_text(json.dumps(cdr()) + "\n")
    output = tmp_path / "candidates.jsonl"
    main(["--recordings-dir", str(recordings), "--cdr-jsonl", str(source), "--output", str(output)])
    assert os.stat(output).st_mode & 0o077 == 0
    assert json.loads(output.read_text())["tenant"] == "t1"
    with pytest.raises(SystemExit) as error:
        main(["--recordings-dir", str(recordings), "--cdr-jsonl", str(source), "--output", str(output)])
    assert error.value.code == 2

@pytest.mark.parametrize("invalid", [None, [], {}, 4, True, ["PJSIP/t1-recepcao-00000001"]])
def test_malformed_cdr_destination_channel_is_ignored_without_crash(tmp_path, invalid):
    recordings = file(tmp_path)
    assert corroborate_cdr(cdr(DestinationChannel=invalid)) is None
    rows, summary = propose_candidates(recordings, [cdr(DestinationChannel=invalid)])
    assert rows == []
    assert summary["proposed"] == 0
