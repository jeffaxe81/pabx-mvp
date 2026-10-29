import hashlib
import json
import os

import pytest

from recording_access import load_recording_policy
from recording_catalog import (
    load_manifest, preview_batch, reconcile_catalog,
)

AUDIO = "20261022-120000-551199998888-1010.wav"


def setup_files(tmp_path):
    media = tmp_path / "media"
    media.mkdir()
    (media / AUDIO).write_bytes(b"RIFF TEST")
    policy = tmp_path / "policy.json"
    value = {"credentials": [{"token_sha256": hashlib.sha256(b"x"*48).hexdigest(),
                "tenant": "t1", "role": "supervisor", "expires_at": 4102444800}],
             "recordings": {}}
    policy.write_text(json.dumps(value), encoding="utf-8")
    policy.chmod(0o600)
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({
        "filename": AUDIO, "tenant": "t1", "owner_extension": "t1-recepcao",
        "source_ref": "CDR-T1-20261022-01"}) + "\n", encoding="utf-8")
    return media, policy, manifest


def test_default_is_read_only_and_does_not_create_lock(tmp_path):
    media, policy, manifest = setup_files(tmp_path)
    before = policy.read_bytes()
    report = reconcile_catalog(policy, media, manifest)
    assert report == {"mode": "dry-run", "new": 1, "unchanged": 0, "total": 1}
    assert policy.read_bytes() == before
    assert not (tmp_path / "policy.json.lock").exists()


def test_apply_atomic_and_preserves_credentials(tmp_path):
    media, policy, manifest = setup_files(tmp_path)
    creds = load_recording_policy(policy)["credentials"]
    assert reconcile_catalog(policy, media, manifest, True)["new"] == 1
    after = load_recording_policy(policy)
    assert after["credentials"] == creds
    assert after["recordings"][AUDIO] == {
        "tenant": "t1", "owner_extension": "t1-recepcao",
        "source_ref": "CDR-T1-20261022-01",
    }
    assert os.stat(policy).st_mode & 0o077 == 0
    assert reconcile_catalog(policy, media, manifest, True)["unchanged"] == 1


def test_cross_tenant_conflict_is_rejected_without_mutation(tmp_path):
    media, policy, manifest = setup_files(tmp_path)
    reconcile_catalog(policy, media, manifest, True)
    before = policy.read_bytes()
    manifest.write_text(json.dumps({
        "filename": AUDIO, "tenant": "t2", "source_ref": "CDR-T2-20261022-01"}) + "\n")
    with pytest.raises(ValueError, match="difere"):
        reconcile_catalog(policy, media, manifest, True)
    assert policy.read_bytes() == before


@pytest.mark.parametrize("update", [
    {"filename": "../outside.wav"},
    {"tenant": "t3", "owner_extension": "t1-recepcao"},
    {"tenant": 3},
    {"source_ref": ""},
    {"extra": "not-allowed"},
])
def test_invalid_manifest_rejected(tmp_path, update):
    media, policy, manifest = setup_files(tmp_path)
    row = json.loads(manifest.read_text())
    row.update(update)
    manifest.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError):
        reconcile_catalog(policy, media, manifest, True)
    assert load_recording_policy(policy)["recordings"] == {}


def test_symlink_file_is_not_importable(tmp_path):
    media, policy, manifest = setup_files(tmp_path)
    outside = tmp_path / "private.wav"
    outside.write_bytes(b"outside")
    (media / AUDIO).unlink()
    (media / AUDIO).symlink_to(outside)
    with pytest.raises(ValueError, match="simbólico"):
        reconcile_catalog(policy, media, manifest, True)


def test_invalid_row_blocks_complete_batch(tmp_path):
    media, policy, manifest = setup_files(tmp_path)
    row = json.loads(manifest.read_text())
    another = dict(row)
    another["filename"] = "missing.wav"
    manifest.write_text(json.dumps(row) + "\n" + json.dumps(another) + "\n")
    with pytest.raises(ValueError):
        reconcile_catalog(policy, media, manifest, True)
    assert load_recording_policy(policy)["recordings"] == {}


def test_duplicate_filename_rejected(tmp_path):
    media, policy, manifest = setup_files(tmp_path)
    manifest.write_text(manifest.read_text() * 2)
    with pytest.raises(ValueError, match="repetido"):
        load_manifest(manifest)


def test_world_readable_policy_rejected(tmp_path):
    media, policy, manifest = setup_files(tmp_path)
    policy.chmod(0o644)
    with pytest.raises(ValueError, match="0600"):
        reconcile_catalog(policy, media, manifest)


def test_policy_symlink_rejected(tmp_path):
    media, policy, manifest = setup_files(tmp_path)
    symlink = tmp_path / "alias.json"
    symlink.symlink_to(policy)
    with pytest.raises(ValueError, match="regular"):
        reconcile_catalog(symlink, media, manifest, True)


def test_no_proof_no_import(tmp_path):
    media, policy, manifest = setup_files(tmp_path)
    row = json.loads(manifest.read_text())
    row.pop("source_ref")
    manifest.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="obrigatórios"):
        reconcile_catalog(policy, media, manifest)


def test_operator_cannot_set_cross_tenant_owner(tmp_path):
    media, policy, manifest = setup_files(tmp_path)
    row = json.loads(manifest.read_text())
    row["owner_extension"] = "t2-recepcao"
    manifest.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="outra empresa"):
        reconcile_catalog(policy, media, manifest)


def test_symlink_manifest_rejected(tmp_path):
    media, policy, manifest = setup_files(tmp_path)
    alias = tmp_path / "manifest-alias"
    alias.symlink_to(manifest)
    with pytest.raises(ValueError, match="regular"):
        reconcile_catalog(policy, media, alias)

def test_one_source_reference_cannot_classify_two_tenants(tmp_path):
    media, policy, manifest = setup_files(tmp_path)
    other_name = "20261022-120100-551199998888-1010.wav"
    (media / other_name).write_bytes(b"RIFF TEST SECOND")
    first = json.loads(manifest.read_text())
    second = {
        "filename": other_name, "tenant": "t10", "source_ref": first["source_ref"],
        "owner_extension": "t10-recepcao",
    }
    manifest.write_text(json.dumps(first) + "\n" + json.dumps(second) + "\n")
    previous = policy.read_bytes()
    with pytest.raises(ValueError, match="compartilhada entre empresas"):
        reconcile_catalog(policy, media, manifest, True)
    assert policy.read_bytes() == previous


def test_manifest_duplicate_tenant_key_is_rejected(tmp_path):
    media, policy, manifest = setup_files(tmp_path)
    previous = policy.read_bytes()
    raw = manifest.read_text()
    manifest.write_text(raw.replace('"tenant": "t1"', '"tenant": "t10", "tenant": "t1"'))
    with pytest.raises(ValueError, match="JSON"):
        reconcile_catalog(policy, media, manifest, True)
    assert policy.read_bytes() == previous


def test_cross_tenant_reference_reuse_across_separate_imports_is_blocked(tmp_path):
    media, policy, manifest = setup_files(tmp_path)
    assert reconcile_catalog(policy, media, manifest, True)["new"] == 1
    previous = policy.read_bytes()
    other_name = "20261022-120100-551199998888-1010.wav"
    (media / other_name).write_bytes(b"RIFF TEST SECOND")
    first = json.loads(manifest.read_text())
    second = {
        "filename": other_name,
        "tenant": "t10",
        "owner_extension": "t10-recepcao",
        "source_ref": first["source_ref"],
    }
    manifest.write_text(json.dumps(second) + "\n")
    with pytest.raises(ValueError, match="compartilhada"):
        reconcile_catalog(policy, media, manifest, True)
    assert policy.read_bytes() == previous
    assert load_recording_policy(policy)["recordings"][AUDIO]["tenant"] == "t1"

