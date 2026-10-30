"""Emissão, expiração, revogação e persistência segura dos Bearer de fila."""
import os
import stat

import pytest

from queue_access import authenticate_queue, load_queue_policy
from queue_credentials import init_policy, issue_credential, revoke_credential


def test_init_issue_revocation_are_atomic_and_private(tmp_path):
    path = tmp_path / "queue.json"
    assert init_policy(path) == {"initialized": True}
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    issued = issue_credential(path, "t1", "agent", extension="t1-recepcao", now=500, ttl=300)
    assert issued["tenant"] == "t1"
    assert issued["role"] == "agent"
    assert len(issued["token"]) >= 32
    assert issued["token"] not in path.read_text()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    loaded = load_queue_policy(path)
    assert authenticate_queue("Bearer " + issued["token"], loaded, now=700)["tenant"] == "t1"
    assert authenticate_queue("Bearer " + issued["token"], loaded, now=800) is None
    assert revoke_credential(path, issued["sha256"])["revoked"] is True
    assert authenticate_queue("Bearer " + issued["token"], load_queue_policy(path), now=700) is None


def test_issuance_rejects_cross_tenant_extension_and_invalid_role(tmp_path):
    path = tmp_path / "queue.json"
    init_policy(path)
    with pytest.raises(ValueError):
        issue_credential(path, "t1", "agent", extension="t2-recepcao")
    with pytest.raises(ValueError):
        issue_credential(path, "t1", "agent")
    with pytest.raises(ValueError):
        issue_credential(path, "t01", "supervisor")
    with pytest.raises(ValueError):
        issue_credential(path, "t1", "administrator")
    with pytest.raises(ValueError):
        issue_credential(path, "t1", "supervisor", extension="t1-recepcao")
    with pytest.raises(ValueError):
        issue_credential(path, "t1", "agent", extension="t1-recepcao", ttl=299)
    with pytest.raises(ValueError):
        issue_credential(path, "t1", "agent", extension="t1-recepcao", ttl=86401)


def test_init_does_not_overwrite_existing_catalog(tmp_path):
    path = tmp_path / "queue.json"
    init_policy(path)
    old = path.read_bytes()
    with pytest.raises(ValueError, match="já existe"):
        init_policy(path)
    assert path.read_bytes() == old


def test_world_readable_catalog_is_denied(tmp_path):
    path = tmp_path / "queue.json"
    init_policy(path)
    path.chmod(0o644)
    assert load_queue_policy(path) is None
    with pytest.raises(ValueError, match="privado"):
        issue_credential(path, "t1", "supervisor")


def test_catalog_symlink_is_not_accepted(tmp_path):
    legit = tmp_path / "legit.json"
    init_policy(legit)
    linked = tmp_path / "linked.json"
    linked.symlink_to(legit)
    assert load_queue_policy(linked) is None
    with pytest.raises(ValueError):
        issue_credential(linked, "t1", "supervisor")
    with pytest.raises(ValueError):
        init_policy(linked)


def test_revoke_never_silently_accepts_unknown_hash(tmp_path):
    path = tmp_path / "queue.json"
    init_policy(path)
    with pytest.raises(ValueError):
        revoke_credential(path, "0"*64)
    with pytest.raises(ValueError):
        revoke_credential(path, "bad")


def test_issuance_rejects_invalid_clock_and_role_without_creating_token(tmp_path):
    path = tmp_path / "queue.json"
    init_policy(path)
    original = path.read_bytes()
    for now in (True, False, "1000", None if False else [], float("nan"), float("inf"), -1):
        with pytest.raises(ValueError):
            issue_credential(path, "t1", "supervisor", now=now)
    for role in ([], {}, ["agent"], 2, None):
        with pytest.raises(ValueError):
            issue_credential(path, "t1", role, now=1000)
    assert path.read_bytes() == original
    assert issue_credential(path, "t1", "supervisor", now=1000)["expires_at"] == 4600


def test_queue_catalog_rejects_duplicate_json_fields(tmp_path):
    path = tmp_path / "queue-credentials.json"
    path.write_text('{"credentials":[],"credentials":[]}', encoding="utf-8")
    path.chmod(0o600)
    assert load_queue_policy(path) is None


def test_queue_credential_listing_never_exposes_plaintext(tmp_path):
    from queue_credentials import list_credential_metadata
    path = tmp_path / "queue-credentials.json"
    init_policy(path)
    issued = issue_credential(path, "t1", "agent", extension="t1-1001", now=1000)
    listed = list_credential_metadata(path)
    assert len(listed) == 1
    assert listed[0]["sha256"] == issued["sha256"]
    assert listed[0]["tenant"] == "t1"
    assert "token" not in listed[0]
    assert issued["token"] not in str(listed)
