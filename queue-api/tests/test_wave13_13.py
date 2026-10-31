from monitoring_access import scoped_monitoring_entries

def test_monitoring_snapshot_nested_data_cannot_change_store():
    source=[{"tenant":"t1","details":{"quality":[1,2]}},{"tenant":"t10","details":{"quality":[3]}}]
    result=scoped_monitoring_entries(source,"t1")
    result[0]["details"]["quality"].append(999)
    assert source[0]["details"]["quality"] == [1,2]
    assert scoped_monitoring_entries(source,"t10")[0]["details"]["quality"] == [3]
