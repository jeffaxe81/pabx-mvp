import hashlib
import json
import time

from recording_access import (
    load_recording_policy, authenticate_recordings,
    can_read_recording, allowed_browser_origin,
)

TOKEN = "a" * 48
FILE_T1 = "20261022-120000-111-1010.wav"
FILE_T2 = "20261022-120100-222-1010.wav"


def policy():
    return {
        "credentials": [
            {"token_sha256": hashlib.sha256(TOKEN.encode()).hexdigest(),
             "tenant": "t1", "role": "agent", "extension": "t1-1010",
             "expires_at": 4102444800},
        ],
        "recordings": {
            FILE_T1: {"tenant": "t1", "owner_extension": "t1-1010"},
            FILE_T2: {"tenant": "t2", "owner_extension": "t2-1010"},
            "legacy.wav": {"tenant": "t1"},
        },
    }


def test_policy_missing_or_invalid_json_fails_closed(tmp_path):
    p = tmp_path / "policy.json"
    assert load_recording_policy(p) is None
    p.write_text("{bad", encoding="utf-8")
    assert load_recording_policy(p) is None


def test_policy_loads_only_valid_schema(tmp_path):
    p = tmp_path / "policy.json"
    p.write_text(json.dumps(policy()))
    assert load_recording_policy(p) == policy()
    obj = policy()
    obj["credentials"][0]["expires_at"] = True
    p.write_text(json.dumps(obj))
    assert load_recording_policy(p) is None
    obj["credentials"][0]["expires_at"] = 4102444800
    obj["credentials"][0]["role"] = ["admin"]
    p.write_text(json.dumps(obj))
    assert load_recording_policy(p) is None


def test_missing_manifest_tenant_and_filename_never_fallback():
    principal = {"role": "admin", "tenant": "t1"}
    assert can_read_recording(policy(), principal, FILE_T1)
    assert not can_read_recording(policy(), principal, FILE_T2)
    assert not can_read_recording(policy(), principal, "unknown.wav")


def test_agent_must_be_recording_owner():
    p = policy()
    owner = {"role": "agent", "tenant": "t1", "extension": "t1-1010"}
    other = {"role": "agent", "tenant": "t1", "extension": "t1-1001"}
    assert can_read_recording(p, owner, FILE_T1)
    assert not can_read_recording(p, other, FILE_T1)
    assert not can_read_recording(p, owner, "legacy.wav")


def test_wrong_missing_or_expired_bearer_rejected():
    p = policy()
    for header in (None, "", "Basic "+TOKEN, "Bearer short", "Bearer "+("x"*48)):
        assert authenticate_recordings(header, p, now=1000) is None
    assert authenticate_recordings("Bearer "+TOKEN, p, now=4102444800) is None
    assert authenticate_recordings("Bearer "+TOKEN, p, now=1000)["tenant"] == "t1"


def test_cors_exact_origin_only():
    origins = {"https://pabx.example.org", "http://localhost:8082"}
    assert allowed_browser_origin("https://pabx.example.org", origins)
    for origin in ("https://pabx.example.org.attacker.test", "null",
                   "https://pabx.example.org/path", "http://pabx.example.org", "*"):
        assert not allowed_browser_origin(origin, origins)


def test_no_filename_path_traversal(tmp_path):
    p = tmp_path / "policy.json"
    obj = policy()
    obj["recordings"]["../secret.wav"] = {"tenant": "t1"}
    p.write_text(json.dumps(obj))
    assert load_recording_policy(p) is None
