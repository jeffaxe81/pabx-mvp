from monitoring_access import scoped_monitoring_entries

def test_monitoring_snapshots_do_not_modify_source_on_mutation():
    records = [{"tenant":"t1","type":"alert"},{"tenant":"t10","type":"alarm"}]
    selected = scoped_monitoring_entries(records,"t1")
    assert len(selected) == 1
    selected[0]["type"] = "corrupted"
    assert records[0]["type"] == "alert"
    assert scoped_monitoring_entries(records,"t10") == [{"tenant":"t10","type":"alarm"}]

def test_monitoring_rejects_broken_tenant_selector():
    assert scoped_monitoring_entries([{"tenant":"t1"}],"t1 extra") == []
    assert scoped_monitoring_entries(None, "t1") == []
