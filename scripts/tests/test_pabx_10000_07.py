"""AXE PABX puro: 1.000 caixas postais e PINs distintos; offline."""
import json
import pytest
from voicemail_pin_audit import audit_voicemail_text

@pytest.mark.parametrize("case",[pytest.param(i,id=f"AXE-{i+6001:05d}") for i in range(1000)])
def test_voicemail_1000_distinct_private_pin_and_tenant_records(case):
    pin=str(91340000+case)
    # O PIN contém ao menos três algarismos diferentes em todos os casos.
    mailbox=f"t3-ramal-{case:04d}"
    context="[t3]" if case<500 else "[t4]"
    src=f"{context}\n{mailbox} => {pin},Ramal-{case:04d}\n"
    report=audit_voicemail_text(src)
    assert report is not None and report["mailboxes"]==1
    assert pin not in json.dumps(report)
    if case<500:
        assert report["ok"] and report["cross_tenant"]==0
    else:
        assert not report["ok"] and report["cross_tenant"]==1
