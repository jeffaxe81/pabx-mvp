"""Atalho *97: mailbox do endpoint SIP autenticado, nao do CallerID.

Prova de contrato estatico. O aceite de runtime Asterisk e separado.
"""
from pathlib import Path
import re

import pytest
from tenants import render_tenant_extensions

STATIC = Path(__file__).resolve().parents[2] / "asterisk" / "extensions.conf"


def voicemail_route(source, tenant):
    section = re.search(
        r"(?ms)^\[" + re.escape(tenant) + r"-internal\]\s*\n(.*?)(?=^\[|\Z)",
        source,
    )
    if not section:
        return None
    found = re.search(
        r"(?ms)^exten\s*=>\s*\*97,1,[^\n]*\n"
        r"(?:\s*same\s*=>[^\n]*\n)*",
        section.group(1),
    )
    if not found:
        return None
    return [line.strip() for line in found.group(0).splitlines() if line.strip()]


def voicemail_guard_is_safe(source, tenant):
    lines = voicemail_route(source, tenant)
    if lines is None:
        return False
    expected = [
        "exten => *97,1,Set(VM_ENDPOINT=${CHANNEL(endpoint)})",
        'same => n,GotoIf($["${VM_ENDPOINT}" = ""]?voicemail-negado)',
        'same => n,GotoIf($["${PJSIP_ENDPOINT(${VM_ENDPOINT},context)}"'
        f' != "{tenant}-internal"]?voicemail-negado)',
        'same => n,GotoIf($["${PJSIP_ENDPOINT(${VM_ENDPOINT},mailboxes)}"'
        f' != "${{VM_ENDPOINT}}@{tenant}"]?voicemail-negado)',
        f"same => n,VoiceMailMain(${{VM_ENDPOINT}}@{tenant})",
        "same => n,Hangup()",
        "same => n(voicemail-negado),Hangup(21)",
    ]
    return lines == expected


@pytest.mark.parametrize("tenant", ("t1", "t2"))
def test_versioned_context_binds_mailbox_to_authenticated_endpoint(tenant):
    assert voicemail_guard_is_safe(STATIC.read_text(encoding="utf-8"), tenant)


@pytest.mark.parametrize("tenant", ("t3", "t4", "t10", "t25"))
def test_wizard_uses_same_guard_for_future_tenants(tenant):
    assert voicemail_guard_is_safe(render_tenant_extensions(tenant), tenant)


@pytest.mark.parametrize("tenant", ("t1", "t2", "t3", "t10"))
def test_callerid_is_not_used_for_voicemail_identity(tenant):
    content = (STATIC.read_text(encoding="utf-8") if tenant in {"t1", "t2"}
               else render_tenant_extensions(tenant))
    route = voicemail_route(content, tenant)
    assert route and not any("CALLERID(" in line for line in route)


@pytest.mark.parametrize("mutate", [
    lambda s: s.replace("CHANNEL(endpoint)", "CALLERID(num)", 1),
    lambda s: s.replace("t3-internal", "t2-internal", 1),
    lambda s: s.replace("VM_ENDPOINT}@t3", "VM_ENDPOINT}@t2", 1),
    lambda s: s.replace("mailboxes)", "auth)", 1),
    lambda s: s.replace("voicemail-negado)", "voicemail-liberado)", 1),
    lambda s: s.replace("Hangup(21)", "Hangup()", 1),
    lambda s: s.replace("VoiceMailMain(${VM_ENDPOINT}@t3)", "VoiceMailMain(${CALLERID(num)}@t3)", 1),
    lambda s: s.replace(
        "same => n,VoiceMailMain(${VM_ENDPOINT}@t3)",
        "same => n,VoiceMailMain(${VM_ENDPOINT}@t2)", 1),
    lambda s: s.replace(
        'same => n,GotoIf($["${PJSIP_ENDPOINT(${VM_ENDPOINT},context)}" != "t3-internal"]?voicemail-negado)\n',
        "", 1),
    lambda s: s.replace(
        'same => n,GotoIf($["${PJSIP_ENDPOINT(${VM_ENDPOINT},mailboxes)}" != "${VM_ENDPOINT}@t3"]?voicemail-negado)\n',
        "", 1),
    lambda s: s.replace(
        "same => n,VoiceMailMain(${VM_ENDPOINT}@t3)",
        "same => n,VoiceMailMain(${VM_ENDPOINT}@t3)\n same => n,VoiceMailMain(${CALLERID(num)}@t3)", 1),
])
def test_mutations_break_contract(mutate):
    original = render_tenant_extensions("t3")
    altered = mutate(original)
    assert altered != original
    assert not voicemail_guard_is_safe(altered, "t3")
