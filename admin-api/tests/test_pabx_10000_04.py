"""1.000 casos de DIDs exclusivos e colisões entre empresas."""
import pytest
from tenants import validate_tenant_creation_input

@pytest.mark.parametrize("case", [
    pytest.param(i,id=f"AXE-{i+3001:05d}") for i in range(1000)
])
def test_did_1000_distinct_numbers_and_tenant_collision(case):
    tenant="t"+str(3+case)
    did=str(5511901000000+case)
    input_data={"tenant_id":tenant,"did":did,"display_name":f"Empresa {case:04d}"}
    if case<500:
        existing=[{"tenant_id":"t2000","did":"5511909999999"}]
        ok,_,item=validate_tenant_creation_input(input_data,existing)
        assert ok and item==input_data
    else:
        # O DID já está associado a outra empresa, mesmo que ID seja novo.
        existing=[{"tenant_id":"t2000","did":did}]
        ok,_,item=validate_tenant_creation_input(input_data,existing)
        assert not ok and item is None
