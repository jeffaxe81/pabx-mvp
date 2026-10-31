from insights_common import tenant_rows

def test_insights_returns_detached_rows_without_cross_tenant_mutation():
    rows = [{"tenant":"t1", "duration":12}, {"tenant":"t10", "duration":42}]
    selected = tenant_rows(rows, "t1")
    assert selected == [{"tenant":"t1", "duration":12}]
    selected[0]["tenant"] = "t10"
    selected[0]["duration"] = 999
    assert rows[0] == {"tenant":"t1", "duration":12}
    assert tenant_rows(rows, "t10") == [{"tenant":"t10", "duration":42}]

def test_agent_insights_rows_are_also_detached():
    rows = [{"extension":"t1-recepcao", "duration_seconds":30}]
    result = tenant_rows(rows, "t1", from_agent=True)
    result[0]["duration_seconds"] = 0
    assert rows[0]["duration_seconds"] == 30
