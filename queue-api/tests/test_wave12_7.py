from insights_campaigns import campaign_status_breakdown

def test_campaign_reports_ignore_unhashable_malformed_status():
    records = [{"tenant":"t1","agent_extension":"t1-1001","contacts":[
        {"status":["pendente"],"attempts":0},
        {"status":{"x":1},"attempts":0},
        {"status":"pendente","attempts":0}]},
        {"tenant":"t10","agent_extension":"t10-1001","contacts":[{"status":"atendida","attempts":1}]}]
    counts = campaign_status_breakdown(records,"t1")
    assert counts["pendente"] == 1
    assert counts["atendida"] == 0
