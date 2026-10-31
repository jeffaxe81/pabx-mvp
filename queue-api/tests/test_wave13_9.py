from quality_monitoring import QualityLog

def test_quality_log_only_poor_flag_must_be_boolean():
    log = QualityLog()
    log.append({"channel":"CH1","jitter_ms":10}, poor=False)
    log.append({"channel":"CH2","jitter_ms":50}, poor=True)
    for invalid in (1, "true", None, [], {}):
        assert log.list(only_poor=invalid) == []
    assert [r["channel"] for r in log.list(only_poor=True)] == ["CH2"]
