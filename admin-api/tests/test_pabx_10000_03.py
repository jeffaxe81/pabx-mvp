"""AXE PABX puro: 1.000 combinações ramal/empresa e conflito."""
import pytest
from store import validate_extension_input

@pytest.mark.parametrize("case",[pytest.param(i,id=f"AXE-{i+2001:05d}") for i in range(1000)])
def test_extension_registration_and_1000_tenant_number_combinations(case):
    slot=case%500
    tenant=f"t{3+slot//100}"
    other=f"t{8+slot//100}"
    number=1100+slot%100
    payload={"name":f"novo-{case:04d}","number":number,
             "display_name":f"Ramal {case:04d}",
             "password":f"AXEsecure-{case:04d}-2026","tenant":tenant}
    owner=other if case<500 else tenant
    existing=[{"name":f"old-{case:04d}","number":number,
               "tenant":owner,"voicemail_pin":"93847261"}]
    ok,_,record=validate_extension_input(
        payload,existing,allowed_tenants={tenant,other})
    if case<500:
        assert ok and record["tenant"]==tenant and record["number"]==number
    else:
        assert not ok and record is None
