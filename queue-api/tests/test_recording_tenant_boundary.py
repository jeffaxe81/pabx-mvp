"""Testes negativos de isolamento do catálogo de gravações.

Não substituem as tentativas HTTP com usuários reais nem homologação.
"""
import hashlib
import json

import pytest

from recording_access import can_read_recording, load_recording_policy

FILE = "chamada.wav"


def policy(tenant="t1", role="agent", extension="t1-1010",
           owner_extension="t1-1010"):
    credential = {
        "token_sha256": hashlib.sha256(b"token-de-teste").hexdigest(),
        "tenant": tenant,
        "role": role,
        "expires_at": 4102444800,
    }
    if role == "agent":
        credential["extension"] = extension
    return {
        "credentials": [credential],
        "recordings": {FILE: {
            "tenant": tenant,
            "owner_extension": owner_extension,
        }},
    }


def test_owner_and_agent_matching_tenant_are_accepted(tmp_path):
    p = tmp_path / "policy.json"
    valid = policy()
    p.write_text(json.dumps(valid))
    assert load_recording_policy(p) == valid
    assert can_read_recording(valid, valid["credentials"][0], FILE)


@pytest.mark.parametrize("extension", [
    "t2-1010", "t10-1010", "t1", "t1-", "../t1-1010",
    "t1-1010\n", 1010, None,
])
def test_invalid_agent_extension_denied_even_when_catalog_was_modified(
    tmp_path, extension,
):
    invalid = policy(extension=extension)
    p = tmp_path / "policy.json"
    p.write_text(json.dumps(invalid))
    assert load_recording_policy(p) is None
    assert not can_read_recording(invalid, invalid["credentials"][0], FILE)


@pytest.mark.parametrize("owner_extension", [
    "t2-1010", "t10-1010", "t1", "t1-", "t1-1010/../",
    "", 1010,
])
def test_misclassified_recording_owner_denied_for_agent_and_admin(
    tmp_path, owner_extension,
):
    invalid = policy(owner_extension=owner_extension)
    p = tmp_path / "policy.json"
    p.write_text(json.dumps(invalid))
    assert load_recording_policy(p) is None
    agent = invalid["credentials"][0]
    admin = {"role": "admin", "tenant": "t1"}
    assert not can_read_recording(invalid, agent, FILE)
    assert not can_read_recording(invalid, admin, FILE)


def test_other_tenant_never_reads_even_with_same_extension_number():
    valid = policy()
    for role in ("admin", "supervisor", "agent"):
        assert not can_read_recording(
            valid, {"tenant": "t2", "role": role, "extension": "t2-1010"}, FILE
        )


def test_nong_agent_credential_cannot_carry_foreign_extension(tmp_path):
    invalid = policy(role="supervisor")
    invalid["credentials"][0]["extension"] = "t2-1010"
    p = tmp_path / "policy.json"
    p.write_text(json.dumps(invalid))
    assert load_recording_policy(p) is None


def test_policy_symlink_is_rejected(tmp_path):
    real = tmp_path / "real.json"
    real.write_text(json.dumps(policy()))
    linked = tmp_path / "linked.json"
    linked.symlink_to(real)
    assert load_recording_policy(linked) is None


def test_policy_with_unclassified_owner_still_denies_agent(tmp_path):
    valid = policy()
    valid["recordings"][FILE].pop("owner_extension")
    p = tmp_path / "policy.json"
    p.write_text(json.dumps(valid))
    assert load_recording_policy(p) == valid
    assert not can_read_recording(valid, valid["credentials"][0], FILE)
    assert can_read_recording(valid, {"tenant": "t1", "role": "supervisor"}, FILE)
