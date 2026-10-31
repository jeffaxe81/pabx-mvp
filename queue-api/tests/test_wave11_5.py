from insights_quality_export import quality_average_jitter, quality_average_rtt

def test_quality_export_skips_extreme_rtpc_outliers():
    records = [
      {"channel":"PJSIP/t1-1001-00000001","jitter_ms":"10","rtt_ms":"20"},
      {"channel":"PJSIP/t1-1001-00000002","jitter_ms":"1e308","rtt_ms":"1e308"},
      {"channel":"PJSIP/t10-1001-00000001","jitter_ms":"999","rtt_ms":"999"}]
    assert quality_average_jitter(records, "t1") == {"samples":1, "average_jitter_ms":10.0}
    assert quality_average_rtt(records, "t1") == {"samples":1, "average_rtt_ms":20.0}

def test_rtcp_maximum_is_included_as_valid_measurement():
    row = [{"channel":"PJSIP/t2-1001-00000001","jitter_ms":60000,"rtt_ms":60000}]
    assert quality_average_jitter(row, "t2")["average_jitter_ms"] == 60000.0
