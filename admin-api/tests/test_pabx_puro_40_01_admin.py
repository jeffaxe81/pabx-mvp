"""Bateria PABX puro #01-10: contrato estático/local; não homologa SIP real."""
import stat
import pytest
from ami_protocol import build_action, parse_ami_blocks
from auth import SessionStore, hash_password, verify_password
from store import validate_extension_input
from tenant_provisioning import build_tenant_files
from tenant_registry_recovery import snapshot_registry, restore_registry


def test_01_ami_login_frame_terminates_once():
    assert build_action({"Action": "Login", "Username": "operator"}) == (
        "Action: Login\r\nUsername: operator\r\n\r\n"
    )


def test_02_ami_header_value_cannot_inject_action():
    with pytest.raises(ValueError):
        build_action({"Action": "Ping\r\nAction: Originate"})


def test_03_ami_refuses_empty_action_map():
    with pytest.raises(ValueError):
        build_action({})


def test_04_ami_parses_two_distinct_response_frames():
    raw = ("Response: Success\r\nMessage: Ready\r\n\r\n"
           "Event: FullyBooted\r\nPrivilege: system\r\n\r\n")
    frames = parse_ami_blocks(raw)
    assert len(frames) == 2
    assert frames[0]["Response"] == "Success"
    assert frames[1]["Event"] == "FullyBooted"


def test_05_admin_session_expires_at_exact_boundary():
    now = [100.0]
    store = SessionStore(ttl_seconds=30, clock=lambda: now[0])
    token = store.create("operator", role="admin")
    now[0] = 129.0
    assert store.validate(token) == "operator"
    now[0] = 130.0
    assert store.validate(token) is None


def test_06_revoked_admin_token_cannot_be_reused():
    store = SessionStore()
    token = store.create("admin")
    store.revoke(token)
    assert store.validate(token) is None
    assert store.get_role(token) is None


def test_07_admin_password_hash_has_unique_salt():
    first = hash_password("senha-comprida-de-teste")
    second = hash_password("senha-comprida-de-teste")
    assert first != second
    assert verify_password("senha-comprida-de-teste", first)
    assert not verify_password("senha-incorreta", first)


def test_08_same_extension_number_isolated_by_tenant():
    info = {"name": "novo-ramal", "number": 1112, "display_name": "Ramal",
            "password": "senha-forte-2026", "tenant": "t2"}
    existing = [{"name": "outro-ramal", "number": 1112, "tenant": "t1"}]
    ok, _, normalized = validate_extension_input(info, existing)
    assert ok and normalized["tenant"] == "t2"


def test_09_tenant_path_traversal_denied_before_file_generation(tmp_path):
    for bad in ("t1/../../secret", "t0", "t10\nInjected"):
        with pytest.raises(ValueError):
            build_tenant_files(tmp_path, bad, {}, {})
    assert not list(tmp_path.iterdir())


def test_10_registry_rollback_restores_exact_content_and_permissions(tmp_path):
    target = tmp_path / "tenants.json"
    original = b'[{"tenant_id":"t3","did":"5511900011111"}]\n'
    target.write_bytes(original)
    target.chmod(0o600)
    before = snapshot_registry(target)
    target.write_bytes(b"[]")
    restore_registry(target, before)
    assert target.read_bytes() == original
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
