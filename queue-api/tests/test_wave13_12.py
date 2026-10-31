from insights_campaigns import _campaigns, campaign_completion_rate

def test_campaign_snapshots_do_not_copy_private_contact_details():
    rows = [{"tenant":"t1","agent_extension":"t1-1001","contacts":[
        {"status":"atendida","attempts":1,"phone":"5511999888777",
         "customer_name":"private","token":"secret"}]}]
    result = _campaigns(rows,"t1")
    assert result[0]["contacts"] == [{"status":"atendida","attempts":1}]
    assert campaign_completion_rate(rows,"t1")["finished"] == 1
    result[0]["contacts"][0]["status"]="changed"
    assert rows[0]["contacts"][0]["status"]=="atendida"
