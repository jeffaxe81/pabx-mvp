"""Prova de emissão de CDR accountcode nos templates dos novos tenants."""
from conf_generator import render_extensions_dynamic_dial
from tenants import render_tenant_extensions


def test_tenant_dynamic_dial_cdr_tag_precedes_dial():
    data = [{"name": "t3-atendente", "tenant": "t3", "number": 1019}]
    dial = render_extensions_dynamic_dial(data)
    assert "Set(CDR(accountcode)=t3)" in dial
    assert dial.index("Set(CDR(accountcode)=t3)") < dial.index("Dial(PJSIP/t3-atendente")


def test_generated_tenant_queue_and_direct_calls_are_tagged():
    text = render_tenant_extensions("t3")
    assert "Set(CDR(accountcode)=t3)" in text
    assert text.count("Set(CDR(accountcode)=t3)") >= 3
    assert text.index("Set(CDR(accountcode)=t3)") < text.index("Queue(")


def test_tenants_never_share_accountcode():
    first = render_tenant_extensions("t3")
    second = render_tenant_extensions("t4")
    assert "Set(CDR(accountcode)=t4)" not in first
    assert "Set(CDR(accountcode)=t3)" not in second
