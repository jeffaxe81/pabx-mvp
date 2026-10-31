import pytest
from insights_callback_health import callback_pending_over_24h, callback_pending_over_48h

def test_callback_health_age_is_reproducible_and_tenant_scoped():
    rows=[{"id":"a1","tenant":"t1","status":"pendente","attempts":0,"requested_at":1000},
          {"id":"a2","tenant":"t1","status":"pendente","attempts":0,"requested_at":100000},
          {"id":"a3","tenant":"t10","status":"pendente","attempts":0,"requested_at":1000}]
    result=callback_pending_over_24h(rows,"t1",as_of=100000)
    assert result["dated_pending"]==2 and result["at_least_24h"]==1
    assert callback_pending_over_48h(rows,"t1",as_of=100000)["at_least_48h"]==0
    for invalid in (True,None if False else float("nan"),"100000"):
        with pytest.raises(ValueError):
            callback_pending_over_24h(rows,"t1",as_of=invalid)
