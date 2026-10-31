"""1.000 casos únicos: inclusão/duplicidade de ramais com faixas t3..t7."""
import pytest
from store import validate_extension_input

@pytest.mark.parametrize("case", [
    pytest.param(i,id=f"AXE-{i+2001:05d}") for i in range(1000)
])
def test_extension_1000_tenant_specific_number_constraints(case):
    slot=case%500
    tenant="t"+str(3+(slot//100))
    number=1100+(slot%100)
    record={
        "name":f"novo-{case:04d}",
        "number":number,
        "display_name":f"Ramal {case:04d}",
        "password":f"AXEsecure-{case:04d}-2026",
        "tenant":tenant,
    }
    if case<500:
        # O mesmo número é permitido no tenant vizinho.
        neighbour="t"+str(8+(slot//100))
        existing=[{"name":f"old-{case:04d}","number":number,
                   "tenant":neighbour,"voicemail_pin":"93847261"}]
        ok,_,normalized=validate_extension_input(
            record,existing,allowed_tenants={tenant,neighbour})
        assert ok and normalized["number"]==number
        assert normalized["tenant"]==tenant and normalized["name"]==record["name"]
    else:
        # Mesmo número e mesmo tenant: jamais gerar rota ambígua.
        existing=[{"name":f"old-{case:04d}","number":number,
                   "tenant":tenant,"voicemail_pin":"93847261"}]
        ok,_,normalized=validate_extension_input(
            record,existing,allowed_tenants={tenant})
        assert not ok and normalized is None
