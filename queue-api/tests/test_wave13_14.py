from insights_common import tenant_rows

def test_tenant_rows_detaches_nested_values():
    rows=[{"tenant":"t1","payload":{"trace":[1,2]}},
          {"tenant":"t10","payload":{"trace":[3]}}]
    selected=tenant_rows(rows,"t1")
    selected[0]["payload"]["trace"].append(5)
    assert rows[0]["payload"]["trace"] == [1,2]
    assert tenant_rows(rows,"t10")[0]["payload"]["trace"] == [3]
