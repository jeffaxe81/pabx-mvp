from quality_monitoring import QualityLog

def test_quality_log_allowlists_fields_and_keeps_tenant_for_filtering():
    log = QualityLog()
    original = {"channel":"PJSIP/t1-1001-aa12", "tenant":"t1",
                "jitter_ms":"12.5", "caller_id_num":"5511999888777",
                "secret":{"token":"private"}, "packet_loss_percent":"0.5"}
    assert log.append(original, poor=False)
    row = log.list()[0]
    assert row["tenant"] == "t1"
    assert row["jitter_ms"] == 12.5
    assert row["packet_loss_percent"] == 0.5
    assert "caller_id_num" not in row and "secret" not in row
    assert original["jitter_ms"] == "12.5"

def test_quality_log_discards_malformed_tenant_and_payload():
    log = QualityLog()
    assert not log.append({"channel":"bad\nInjected"}, poor=True)
    assert log.append({"channel":"CH1","tenant":"t1\nextra"}, poor=True)
    assert "tenant" not in log.list()[0]
