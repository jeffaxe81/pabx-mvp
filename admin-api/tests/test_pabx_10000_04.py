"""AXE PABX puro: 1.000 cenários de DID associado ao tenant correto."""
import pytest
from tenants import validate_tenant_creation_input

@pytest.mark.parametrize("case",[pytest.param(i,id=f"AXE-{i+3001:05d}") for i in range(1000)])
def test_did_ownership_on_1000_distinct_tenant_numbers(case):
    tenant=f"t{3+case}"
    did=str(5511901000000+case)
    payload={"tenant_id":tenant,"did":did,"display_name":f"Empresa {case:04d}"}
    conflicting="5511909999999" if case<500 else did
    current=[{"tenant_id":"t2000","did":conflicting}]
    ok,_,normalized=validate_tenant_creation_input(payload,current)
    if case<500:
        assert ok and normalized==payload
    else:
        assert not ok and normalized is None
