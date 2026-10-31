from quality_monitoring import parse_quality_event

def test_rtcp_channel_with_ambiguous_spaces_rejected():
    event = {"Event": "UserEvent", "UserEvent": "QualityStats", "Jitter": "2"}
    for channel in ("PJSIP/t1 1001", " PJSIP/t1-1001", "PJSIP/t1-1001 "):
        assert parse_quality_event({**event, "Channel": channel}) is None
    assert parse_quality_event({**event, "Channel": "PJSIP/t1-1001-abc"})["jitter_ms"] == 2.0
