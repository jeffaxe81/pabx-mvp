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


def test_authentication_rejects_in_memory_corruption_without_exception():
    original = policy()
    identity = "Bearer " + TOKEN
    cases = [
        {},
        {"credentials": None},
        {"credentials": "not-a-list"},
        {"credentials": [None]},
        {"credentials": [original["credentials"][0], None]},
        {"credentials": [{**original["credentials"][0], "tenant": "t2"}]},
        {"credentials": [{**original["credentials"][0], "role": ["admin"]}]},
        {"credentials": [{**original["credentials"][0], "expires_at": True}]},
        {"credentials": [{**original["credentials"][0], "expires_at": float("nan")}]},
        {"credentials": [{**original["credentials"][0], "extension": "t2-1010"}]},
        {"credentials": original["credentials"] * 2},
    ]
    for malformed in cases:
        assert authenticate_recordings(identity, malformed, now=1000) is None
    assert authenticate_recordings(identity, original, now="not-a-time") is None
    assert authenticate_recordings(identity, original, now=float("inf")) is None
    assert authenticate_recordings(identity, original, now=1000)["tenant"] == "t1"


def test_direct_recording_authorization_never_raises_on_invalid_catalog():
    principal = {"tenant": "t1", "role": "supervisor"}
    for malformed in ({}, {"recordings": None}, {"recordings": []},
                      {"recordings": {FILE_T1: None}},
                      {"recordings": {FILE_T1: {"tenant": "t10"}}}):
        assert not can_read_recording(malformed, principal, FILE_T1)
    assert can_read_recording(policy(), principal, FILE_T1)

def test_recording_rejects_unhashable_role_without_exposing_data():
    p = policy()
    for role in ([], {}, ["admin"], {"role": "supervisor"}, None, 7):
        assert can_read_recording(p, {"tenant": "t1", "role": role}, FILE_T1) is False
    assert can_read_recording(p, {"tenant": "t1", "role": "supervisor"}, FILE_T1)


def test_cors_policy_malformed_collection_fails_closed():
    for origins in (None, "https://voice.example", 7, {"origin": "https://voice.example"}):
        assert allowed_browser_origin("https://voice.example", origins) is False
    assert allowed_browser_origin("https://voice.example", {"https://voice.example"})

def test_recording_catalog_rejects_malformed_optional_source_provenance(tmp_path):
    good = policy()
    good["recordings"][FILE_T1]["source_ref"] = "CDR:1792670400.123"
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(good))
    assert load_recording_policy(path) == good
    for bad in ([], {}, None, "a", "../bad", "CDR:bad?query",
                "x\nInjected", "x" * 101):
        copy = policy()
        copy["recordings"][FILE_T1]["source_ref"] = bad
        path.write_text(json.dumps(copy))
        if bad is None:
            # Ausente/None preserva formato legado, sem atribuir prova falsa.
            assert load_recording_policy(path) == copy
        else:
            assert load_recording_policy(path) is None
