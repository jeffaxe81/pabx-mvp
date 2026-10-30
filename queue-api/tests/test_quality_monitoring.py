from quality_monitoring import parse_quality_event, is_poor_quality, QualityLog

SAMPLE_EVENT = {
    "Event": "UserEvent", "UserEvent": "QualityStats",
    "Channel": "PJSIP/t1-recepcao-00000001",
    "Jitter": "12.5", "PacketLoss": "0.8", "RTT": "45.0",
}


# ---------- parse_quality_event ----------

def test_parses_valid_quality_event():
    quality = parse_quality_event(SAMPLE_EVENT)
    assert quality["channel"] == "PJSIP/t1-recepcao-00000001"
    assert quality["jitter_ms"] == 12.5
    assert quality["packet_loss_percent"] == 0.8
    assert quality["rtt_ms"] == 45.0


def test_ignores_unrelated_events():
    assert parse_quality_event({"Event": "Hangup"}) is None
    assert parse_quality_event({"Event": "UserEvent", "UserEvent": "OutroTipo"}) is None


def test_handles_empty_rtcp_values_gracefully():
    """
    Chamadas muito curtas ou certos codecs não geram RTCP - o
    Asterisk manda string vazia, não deve virar erro nem virar 0.0
    (que pareceria 'qualidade perfeita' por engano).
    """
    event = {**SAMPLE_EVENT, "Jitter": "", "PacketLoss": "", "RTT": ""}
    quality = parse_quality_event(event)
    assert quality["jitter_ms"] is None
    assert quality["packet_loss_percent"] is None
    assert quality["rtt_ms"] is None


def test_handles_missing_fields_gracefully():
    event = {"Event": "UserEvent", "UserEvent": "QualityStats", "Channel": "PJSIP/x-1"}
    quality = parse_quality_event(event)
    assert quality["jitter_ms"] is None


def test_handles_malformed_numeric_value():
    event = {**SAMPLE_EVENT, "Jitter": "não-é-um-número"}
    assert parse_quality_event(event)["jitter_ms"] is None


# ---------- is_poor_quality ----------

def test_good_quality_below_thresholds():
    quality = {"jitter_ms": 5.0, "packet_loss_percent": 0.1, "rtt_ms": 20.0}
    assert is_poor_quality(quality) is False


def test_poor_quality_due_to_jitter():
    quality = {"jitter_ms": 50.0, "packet_loss_percent": 0.1, "rtt_ms": 20.0}
    assert is_poor_quality(quality, jitter_threshold_ms=30.0) is True


def test_poor_quality_due_to_packet_loss():
    quality = {"jitter_ms": 5.0, "packet_loss_percent": 8.0, "rtt_ms": 20.0}
    assert is_poor_quality(quality, packet_loss_threshold_percent=3.0) is True


def test_missing_metrics_never_trigger_false_alarm():
    quality = {"jitter_ms": None, "packet_loss_percent": None, "rtt_ms": None}
    assert is_poor_quality(quality) is False


def test_custom_thresholds_are_respected():
    quality = {"jitter_ms": 15.0, "packet_loss_percent": 1.0, "rtt_ms": 20.0}
    assert is_poor_quality(quality, jitter_threshold_ms=10.0) is True
    assert is_poor_quality(quality, jitter_threshold_ms=20.0) is False


# ---------- QualityLog ----------

def test_quality_log_lists_newest_first():
    log = QualityLog()
    log.append({"channel": "CH1"}, poor=False)
    log.append({"channel": "CH2"}, poor=True)

    result = log.list()
    assert [e["channel"] for e in result] == ["CH2", "CH1"]


def test_quality_log_filters_only_poor():
    log = QualityLog()
    log.append({"channel": "CH1"}, poor=False)
    log.append({"channel": "CH2"}, poor=True)

    result = log.list(only_poor=True)
    assert [e["channel"] for e in result] == ["CH2"]


def test_quality_log_respects_max_size():
    log = QualityLog(max_size=3)
    for i in range(5):
        log.append({"channel": f"CH{i}"}, poor=False)
    assert len(log.list(limit=100)) == 3


def test_rejects_nonfinite_negative_and_out_of_range_rtcp_metrics():
    for raw in ("NaN", "Infinity", "-Infinity", "-1", "-0.1", "1e999", "x" * 100):
        quality = parse_quality_event({**SAMPLE_EVENT, "Jitter": raw, "RTT": raw})
        assert quality["jitter_ms"] is None
        assert quality["rtt_ms"] is None
    for raw in ("-1", "100.01", "NaN", "inf", "1e999", "x" * 100):
        assert parse_quality_event({**SAMPLE_EVENT, "PacketLoss": raw})["packet_loss_percent"] is None
    assert parse_quality_event({**SAMPLE_EVENT, "PacketLoss": "100"})["packet_loss_percent"] == 100.0
    assert parse_quality_event({**SAMPLE_EVENT, "Jitter": "0"})["jitter_ms"] == 0.0


def test_quality_parser_rejects_non_object_and_boolean_values():
    assert parse_quality_event(None) is None
    assert parse_quality_event("QualityStats") is None
    q = parse_quality_event({**SAMPLE_EVENT, "Jitter": True, "PacketLoss": False})
    assert q["jitter_ms"] is None
    assert q["packet_loss_percent"] is None


def test_invalid_quality_numbers_do_not_create_false_alarm():
    assert not is_poor_quality({"jitter_ms": float("inf"),
                                "packet_loss_percent": float("nan")})
    assert not is_poor_quality({"jitter_ms": -5, "packet_loss_percent": 105})


def test_quality_requires_bounded_printable_ami_channel():
    for bad in (None, False, [], {}, "", "X" * 161, "PJSIP/x" + chr(13) + chr(10) + "Injected"):
        assert parse_quality_event({**SAMPLE_EVENT, "Channel": bad}) is None
    assert parse_quality_event(SAMPLE_EVENT)["channel"] == SAMPLE_EVENT["Channel"]


def test_poor_quality_ignores_non_object_measurements():
    for data in (None, [], {}, False, "jitter", 12):
        assert is_poor_quality(data) is False

# Programa 30 frentes — RTCP: cinco garantias de qualidade.
def test_30_rtcp_non_dict_quality_cannot_create_alarm():
    for q in (None, [], True, "bad"):
        assert is_poor_quality(q) is False


def test_30_rtcp_invalid_threshold_does_not_raise_false_alarm():
    for bad in (None, False, float("nan"), float("inf"), -1, "30"):
        assert is_poor_quality({"jitter_ms": 50}, jitter_threshold_ms=bad) is False
        assert is_poor_quality({"packet_loss_percent": 10},
                               packet_loss_threshold_percent=bad) is False
    assert is_poor_quality({"packet_loss_percent": 10},
                           packet_loss_threshold_percent=101) is False


def test_30_rtcp_log_rejects_invalid_capacity():
    import pytest
    for capacity in (0, -1, True, None, "10", 10001):
        with pytest.raises(ValueError):
            QualityLog(max_size=capacity)


def test_30_rtcp_log_refuses_bad_reports_and_invalid_flags():
    log = QualityLog()
    for payload in (None, [], "bad", True):
        assert log.append(payload, poor=True) is False
    assert log.append({"channel": "CH1"}, poor=1) is False
    assert log.append({"channel": "CH2"}, poor=True) is True
    assert log.list(only_poor=True)[0]["channel"] == "CH2"


def test_30_rtcp_log_limit_and_copy_preserve_original_reports():
    log = QualityLog(max_size=2)
    log.append({"channel": "CH1"}, poor=False)
    log.append({"channel": "CH2"}, poor=True)
    for invalid in (None, False, -1, "100", 1.5):
        assert log.list(limit=invalid) == []
    record = log.list()[0]
    record["channel"] = "MUTATED"
    assert log.list()[0]["channel"] == "CH2"
    assert [r["channel"] for r in log.list(limit=9999)] == ["CH2", "CH1"]
    assert [r["channel"] for r in log.list(only_poor=True)] == ["CH2"]
