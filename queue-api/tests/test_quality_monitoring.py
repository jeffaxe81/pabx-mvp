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
