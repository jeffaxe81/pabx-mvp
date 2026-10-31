from insights_agent_efficiency import agent_duration_coverage

def test_agent_duration_coverage_is_tenant_scoped_and_excludes_invalid_seconds():
    records=[{"tenant":"t1","operator":"t1-1001","disposition":"ANSWERED","billable_seconds":60},
             {"tenant":"t1","operator":"t1-1001","disposition":"ANSWERED","billable_seconds":None},
             {"tenant":"t1","operator":"t1-1001","disposition":"BUSY"},
             {"tenant":"t10","operator":"t10-1001","disposition":"ANSWERED","billable_seconds":50}]
    assert agent_duration_coverage(records,"t1")=={"t1-1001":{
        "answered":2,"with_valid_duration":1,"without_valid_duration":1,"coverage_percent":50.0}}
    assert "t10-1001" not in agent_duration_coverage(records,"t1")
