"""Nova rodada AXE PABX puro: 1.000 regressões parametrizadas, sem rede.

Dez grupos x cem entradas = 1.000 casos coletados pelo pytest.
Não envolve Contact Center, IA, chamadas SIP reais nem produção.
"""
import stat

import pytest

from auth import SessionStore
from conf_publisher import published_conf_batch
from monitoring import validate_monitoring_pin_input
from store import validate_extension_input
from tenants import (
    render_tenant_extensions,
    render_tenant_pjsip,
    validate_tenant_creation_input,
)


def cases(start):
    return [pytest.param(i, id=f"AXE-PBX-{start + i:05d}") for i in range(100)]


@pytest.mark.parametrize("case", cases(11001))
def test_sessions_expire_at_exact_ttl_boundary(case):
    clock = [10000 + case]
    sessions = SessionStore(ttl_seconds=60, clock=lambda: clock[0])
    token = sessions.create(f"pabx-user-{case:03d}", role="operator")
    assert sessions.validate(token) == f"pabx-user-{case:03d}"
    assert sessions.get_role(token) == "operator"
    clock[0] += 59
    assert sessions.validate(token) == f"pabx-user-{case:03d}"
    clock[0] += 1
    assert sessions.validate(token) is None
    assert sessions.get_role(token) is None


@pytest.mark.parametrize("case", cases(11101))
def test_revoking_session_keeps_another_extension_session(case):
    sessions = SessionStore()
    to_revoke = sessions.create(f"ramal-{case:03d}", role="operator")
    to_keep = sessions.create(f"supervisor-{case:03d}", role="admin")
    assert to_revoke != to_keep
    sessions.revoke(to_revoke)
    assert sessions.validate(to_revoke) is None
    assert sessions.get_role(to_revoke) is None
    assert sessions.validate(to_keep) == f"supervisor-{case:03d}"
    assert sessions.get_role(to_keep) == "admin"


@pytest.mark.parametrize("case", cases(11201))
def test_generated_sip_endpoints_have_own_tenant_auth_and_aor(case):
    tenant = f"t{case + 3}"
    first, second = f"{tenant}-recepcao", f"{tenant}-recepcao-2"
    rendered = render_tenant_pjsip(
        tenant, credentials={first: "A" * 32, second: "B" * 32}
    )
    for endpoint in (first, second):
        assert f"[{endpoint}](endpoint-webrtc)" in rendered
        assert f"auth={endpoint}\n" in rendered
        assert f"aors={endpoint}\n" in rendered
        assert f"mailboxes={endpoint}@{tenant}\n" in rendered
        assert f"username={endpoint}\n" in rendered
    assert rendered.count(f"context={tenant}-internal") == 2
    assert f"context=t{case + 103}-internal" not in rendered


@pytest.mark.parametrize("case", cases(11301))
def test_generated_dialplan_keeps_tenant_voicemail_and_blocklist(case):
    tenant = f"t{case + 3}"
    rendered = render_tenant_extensions(tenant)
    assert f"[{tenant}-internal]" in rendered
    assert f"[{tenant}-hints]" in rendered
    assert f"Set(CDR(accountcode)={tenant})" in rendered
    assert f"DB(blocklist-{tenant}/" in rendered
    assert f"@{tenant})" in rendered
    assert f"#include generated/extensions_dynamic_dial-{tenant}.conf" in rendered
    assert f"PJSIP_ENDPOINT(${{VM_ENDPOINT}},context)" in rendered
    assert "voicemail-negado" in rendered


@pytest.mark.parametrize("case", cases(11401))
def test_monitoring_pin_strong_ascii_numeric_is_allowed(case):
    pin = f"927416{case:02d}"
    ok, error, value = validate_monitoring_pin_input({"pin": pin})
    assert ok and error is None and value == pin


@pytest.mark.parametrize("case", cases(11501))
def test_monitoring_pin_rejects_unicode_digit_spoof(case):
    pin = f"927416{case:02d}"
    at = case % len(pin)
    spoofed = pin[:at] + "９" + pin[at + 1:]
    ok, error, value = validate_monitoring_pin_input({"pin": spoofed})
    assert not ok and error and value is None


@pytest.mark.parametrize("case", cases(11601))
def test_preexisting_static_did_cannot_be_claimed_by_new_tenant(case):
    did = str(5511912000000 + case)
    payload = {
        "tenant_id": f"t{case + 3}",
        "did": did,
        "display_name": f"Empresa {case:03d}",
    }
    ok, error, normalized = validate_tenant_creation_input(
        payload, existing=[], reserved_dids={did}
    )
    assert not ok and error and normalized is None


@pytest.mark.parametrize("case", cases(11701))
def test_extension_number_rejects_non_ascii_numeric_spoof(case):
    canonical = str(1100 + case)
    forged = canonical[:2] + "２" + canonical[3:]
    payload = {
        "name": f"ramal-{case:03d}",
        "number": forged,
        "display_name": f"Ramal {case:03d}",
        "password": f"AXE-PBX-SIP-2026-{case:04d}",
        "tenant": "t3",
    }
    ok, error, record = validate_extension_input(
        payload, existing=[], allowed_tenants={"t3"}
    )
    assert not ok and error and record is None


@pytest.mark.parametrize("case", cases(11801))
def test_config_publisher_preserves_file_mode_on_commit(case, tmp_path):
    filename = f"pabx_t{case:03d}.conf"
    target = tmp_path / filename
    target.write_text("original", encoding="utf-8")
    original_mode = 0o600 if case % 2 else 0o640
    target.chmod(original_mode)
    replacement = f"[t{case + 3}-internal]\n; safe publication {case}\n"
    with published_conf_batch(tmp_path, {filename: replacement}):
        assert target.read_text(encoding="utf-8") == replacement
    assert target.read_text(encoding="utf-8") == replacement
    assert stat.S_IMODE(target.stat().st_mode) == original_mode
    assert not list(tmp_path.glob(".pabx-conf-*"))


@pytest.mark.parametrize("case", cases(11901))
def test_config_publisher_restores_previous_bytes_after_failure(case, tmp_path):
    filename = f"pabx_t{case:03d}.conf"
    target = tmp_path / filename
    original = f"[t{case + 3}-internal]\n; before-{case}\n"
    target.write_text(original, encoding="utf-8")
    original_mode = 0o600 if case % 2 else 0o640
    target.chmod(original_mode)
    with pytest.raises(RuntimeError, match="simulated reload failure"):
        with published_conf_batch(tmp_path, {filename: f"new-{case}"}):
            raise RuntimeError("simulated reload failure")
    assert target.read_text(encoding="utf-8") == original
    assert stat.S_IMODE(target.stat().st_mode) == original_mode
    assert not list(tmp_path.glob(".pabx-conf-*"))
