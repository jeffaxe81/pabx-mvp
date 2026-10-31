import pytest
from fraud_detection import FraudAlertsLog

def test_fraud_alert_list_returns_detached_copy():
    log = FraudAlertsLog(max_size=2)
    log.append("volume_anormal", "t1-1001", "pico")
    row = log.list()[0]
    row["detail"] = "alterado"
    assert log.list()[0]["detail"] == "pico"

def test_fraud_alert_rejects_invalid_limits():
    for raw in (0, -1, True, None, "100", 10001):
        with pytest.raises(ValueError):
            FraudAlertsLog(max_size=raw)
    log = FraudAlertsLog()
    log.append("volume_anormal", "t1-1001", "pico")
    for raw in (0, -1, True, None, 1.5):
        assert log.list(limit=raw) == []
