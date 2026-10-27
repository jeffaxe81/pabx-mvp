"""Regressões do limite de roteamento entre tenants em dialplan e wizard.

São provas estáticas de fonte; a negativa SIP em Asterisk real exige outro gate.
"""
from pathlib import Path
import re

import pytest

from tenants import render_tenant_extensions


DIALPLAN = Path(__file__).resolve().parents[2] / "asterisk" / "extensions.conf"


def route_for(content, tenant):
    """Extrai só a extensão 1000 do contexto interno, sem seguir includes."""
    section = re.search(
        r"(?ms)^\[" + re.escape(tenant) + r"-internal\]\s*\n(.*?)(?=^\[|\Z)",
        content,
    )
    if section is None:
        return None
    match = re.search(
        r"(?ms)^exten\s*=>\s*1000,1,[^\n]*\n(.*?)(?=^exten\s*=>|\Z)",
        section.group(1),
    )
    return match.group(0) if match else None


def queue_boundary_is_safe(content, tenant):
    """Exige âncoras exatas e na ordem; não tenta interpretar Asterisk."""
    body = route_for(content, tenant)
    if body is None:
        return False

    anchor = f"same => n,Set(TENANT={tenant})"
    allowed_en = (
        'same => n,GotoIf($["${FILA_IDIOMA}" = "fila-' + tenant
        + '-en"]?idioma-autorizado)'
    )
    allowed_es = (
        'same => n,GotoIf($["${FILA_IDIOMA}" = "fila-' + tenant
        + '-es"]?idioma-autorizado)'
    )
    fallback = f"same => n,Set(FILA_IDIOMA=fila-{tenant})"
    target = f"same => n(idioma-autorizado),NoOp(Fila validada para {tenant})"
    queue = "same => n,Queue(${FILA_IDIOMA},c,,,${OVERFLOW_TIMEOUT})"
    expected = [anchor, allowed_en, allowed_es, fallback, target, queue]

    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if any(lines.count(statement) != 1 for statement in expected):
        return False
    positions = [lines.index(statement) for statement in expected]
    if positions != sorted(positions) or len(set(positions)) != len(positions):
        return False

    # A mesma extensão não pode redefinir fronteiras depois do gate,
    # inserir Queue antecipadamente ou executar jump incondicional.
    for index, line in enumerate(lines):
        if "Set(TENANT=" in line and line != anchor:
            return False
        if "Set(FILA_IDIOMA=" in line and line != fallback:
            return False
        if "Queue(" in line and line != queue:
            return False
        if line.startswith("same => n,Goto(") and index < positions[-1]:
            return False
    return True


@pytest.mark.parametrize("tenant", ["t1", "t2"])
def test_static_contexts_have_queue_guard(tenant):
    assert queue_boundary_is_safe(DIALPLAN.read_text(encoding="utf-8"), tenant)


@pytest.mark.parametrize("tenant", ["t3", "t4", "t10", "t25"])
def test_wizard_generates_queue_guard_with_exact_tenant(tenant):
    assert queue_boundary_is_safe(render_tenant_extensions(tenant), tenant)


@pytest.mark.parametrize("tenant", ["t1", "t2", "t3", "t10"])
def test_guard_preserves_only_expected_language_routes(tenant):
    content = (DIALPLAN.read_text(encoding="utf-8") if tenant in ("t1", "t2")
               else render_tenant_extensions(tenant))
    body = route_for(content, tenant)
    assert f'"fila-{tenant}-en"]?idioma-autorizado' in body
    assert f'"fila-{tenant}-es"]?idioma-autorizado' in body
    assert f"Set(FILA_IDIOMA=fila-{tenant})" in body
    assert "Queue(${FILA_IDIOMA},c,,,${OVERFLOW_TIMEOUT})" in body


@pytest.mark.parametrize("mutation", [
    lambda body: body.replace("Set(TENANT=t3)", 'Set(TENANT=${TENANT})'),
    lambda body: body.replace("Set(TENANT=t3)", "Set(TENANT=t2)"),
    lambda body: body.replace('"fila-t3-en"]', '"fila-t2-en"]'),
    lambda body: body.replace('"fila-t3-es"]', '"fila-t2-es"]'),
    lambda body: body.replace("Set(FILA_IDIOMA=fila-t3)",
                              "Set(FILA_IDIOMA=fila-t2)"),
    lambda body: body.replace("Set(FILA_IDIOMA=fila-t3)", "NoOp(sem fallback)"),
    lambda body: body.replace("idioma-autorizado)", "outra-prioridade)", 1),
    lambda body: body.replace("same => n,Set(CDR(accountcode)=t3)",
                              "same => n,Set(TENANT=t2)\n"
                              " same => n,Set(CDR(accountcode)=t3)"),
    lambda body: body.replace("same => n,Set(TENANT=t3)",
                              "same => n,Queue(fila-t2)\n"
                              " same => n,Set(TENANT=t3)"),
])
def test_tampering_breaks_static_contract(mutation):
    original = render_tenant_extensions("t3")
    changed = mutation(original)
    assert changed != original
    assert not queue_boundary_is_safe(changed, "t3")
