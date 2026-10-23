import json
import os

import pytest

from recording_access import authenticate_recordings, load_recording_policy
from recording_credentials import (
    issue_credential, list_credential_metadata, revoke_credential,
)


def setup_policy(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({
        "credentials": [],
        "recordings": {"t1.wav": {"tenant": "t1"}},
    }))
    path.chmod(0o600)
    return path


def test_issued_token_authenticates_and_never_persists_plaintext(tmp_path):
    path = setup_policy(tmp_path)
    answer = issue_credential(path, "t1", "supervisor", ttl=600, now=1000)
    policy = load_recording_policy(path)
    assert answer["token"] not in path.read_text()
    assert answer["sha256"] == policy["credentials"][0]["token_sha256"]
    assert authenticate_recordings("Bearer " + answer["token"], policy, now=1001)["tenant"] == "t1"
    assert policy["recordings"] == {"t1.wav": {"tenant": "t1"}}
    assert os.stat(path).st_mode & 0o077 == 0


def test_expiration_respects_requested_ttl(tmp_path):
    path = setup_policy(tmp_path)
    answer = issue_credential(path, "t1", "admin", ttl=300, now=2000)
    assert answer["expires_at"] == 2300
    policy = load_recording_policy(path)
    assert authenticate_recordings("Bearer " + answer["token"], policy, now=2300) is None


def test_revoke_invalidates_token_and_preserves_audio_catalog(tmp_path):
    path = setup_policy(tmp_path)
    answer = issue_credential(path, "t1", "supervisor", ttl=300, now=1000)
    status = revoke_credential(path, answer["sha256"])
    assert status["revoked"]
    assert load_recording_policy(path)["credentials"] == []
    assert load_recording_policy(path)["recordings"]["t1.wav"]["tenant"] == "t1"


def test_listing_exposes_only_hash_and_scope(tmp_path):
    path = setup_policy(tmp_path)
    issued = issue_credential(path, "t1", "agent", extension="t1-recepcao", ttl=600, now=1000)
    listed = list_credential_metadata(path)
    assert listed == [{
        "sha256": issued["sha256"], "tenant": "t1",
        "role": "agent", "extension": "t1-recepcao", "expires_at": 1600,
    }]
    assert issued["token"] not in json.dumps(listed)


@pytest.mark.parametrize("tenant,role,extension,ttl", [
    ("t0", "admin", None, 3600),
    ("t1", "invalid", None, 3600),
    ("t1", "agent", None, 3600),
    ("t1", "agent", "t2-recepcao", 3600),
    ("t1", "supervisor", "t1-recepcao", 3600),
    ("t1", "admin", None, 299),
    ("t1", "admin", None, 86401),
    ("t1", "admin", None, True),
])
def test_unsafe_credential_request_is_rejected(tmp_path, tenant, role, extension, ttl):
    path = setup_policy(tmp_path)
    with pytest.raises(ValueError):
        issue_credential(path, tenant, role, extension, ttl, now=1000)
    assert load_recording_policy(path)["credentials"] == []


def test_wrong_digest_and_missing_credential_refused(tmp_path):
    path = setup_policy(tmp_path)
    with pytest.raises(ValueError):
        revoke_credential(path, "garbage")
    with pytest.raises(ValueError):
        revoke_credential(path, "a"*64)


def test_public_policy_permission_rejected(tmp_path):
    path = setup_policy(tmp_path)
    path.chmod(0o644)
    with pytest.raises(ValueError, match="0600"):
        issue_credential(path, "t1", "admin", now=1000)


def test_credential_limit_is_enforced(tmp_path):
    path = setup_policy(tmp_path)
    item = {
        "token_sha256": "a"*64, "tenant": "t1",
        "role": "admin", "expires_at": 200000,
    }
    many = [{**item, "token_sha256": f"{i:064x}"} for i in range(256)]
    path.write_text(json.dumps({"credentials": many, "recordings": {}}))
    with pytest.raises(ValueError, match="limite"):
        issue_credential(path, "t1", "admin", now=1000)
