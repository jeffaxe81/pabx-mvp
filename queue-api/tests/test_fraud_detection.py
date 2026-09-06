from fraud_detection import (
    CallRateTracker, FraudAlertsLog, is_external_call,
    compute_daily_cost, is_over_spending_limit,
)


# ---------- CallRateTracker ----------

def test_call_rate_not_abnormal_below_threshold():
    clock_value = [1000.0]
    tracker = CallRateTracker(clock=lambda: clock_value[0])
    for i in range(5):
        tracker.track_call("t1-1001", f"055119999{i:05d}")
    assert tracker.is_abnormal("t1-1001", window_seconds=60, threshold=10) is False


def test_call_rate_abnormal_above_threshold():
    clock_value = [1000.0]
    tracker = CallRateTracker(clock=lambda: clock_value[0])
    for i in range(15):
        tracker.track_call("t1-1001", f"055119999{i:05d}")
    assert tracker.is_abnormal("t1-1001", window_seconds=60, threshold=10) is True


def test_call_rate_ignores_calls_outside_window():
    clock_value = [1000.0]
    tracker = CallRateTracker(clock=lambda: clock_value[0])
    for i in range(15):
        tracker.track_call("t1-1001", f"numero{i}")

    clock_value[0] = 1000.0 + 120  # 2 minutos depois - fora da janela de 60s
    assert tracker.is_abnormal("t1-1001", window_seconds=60, threshold=10) is False


def test_call_rate_tracks_extensions_independently():
    tracker = CallRateTracker(clock=lambda: 1000.0)
    for i in range(15):
        tracker.track_call("t1-1001", f"numero{i}")
    for i in range(2):
        tracker.track_call("t1-1002", f"numero{i}")

    assert tracker.is_abnormal("t1-1001") is True
    assert tracker.is_abnormal("t1-1002") is False


def test_call_rate_ignores_empty_extension():
    tracker = CallRateTracker()
    tracker.track_call(None, "12345")
    tracker.track_call("", "12345")
    assert tracker.is_abnormal("") is False


def test_recent_destinations_returns_numbers_in_window():
    tracker = CallRateTracker(clock=lambda: 1000.0)
    tracker.track_call("t1-1001", "5511900001111")
    tracker.track_call("t1-1001", "5511900002222")
    assert tracker.recent_destinations("t1-1001") == ["5511900001111", "5511900002222"]


# ---------- FraudAlertsLog ----------

def test_alerts_log_lists_newest_first():
    log = FraudAlertsLog()
    log.append("volume_anormal", "t1-1001", "15 chamadas em 60s")
    log.append("limite_gasto", "t1-1002", "R$ 120,00 hoje")

    result = log.list()
    assert [a["extension"] for a in result] == ["t1-1002", "t1-1001"]


def test_alerts_log_respects_max_size():
    log = FraudAlertsLog(max_size=3)
    for i in range(5):
        log.append("volume_anormal", f"ramal-{i}", "detalhe")
    assert len(log.list(limit=100)) == 3


# ---------- is_external_call ----------

def test_is_external_call_true_for_gateway_channels():
    assert is_external_call({"DestChannel": "PJSIP/5511999998888@gateway-tdm-00000001"}) is True
    assert is_external_call({"DestChannel": "PJSIP/5511999998888@gateway-tdm-2-00000001"}) is True


def test_is_external_call_false_for_internal_channels():
    assert is_external_call({"DestChannel": "PJSIP/t1-1001-00000001"}) is False


def test_is_external_call_false_when_missing():
    assert is_external_call({}) is False


# ---------- compute_daily_cost / is_over_spending_limit ----------

def test_compute_daily_cost_sums_only_answered_calls():
    records = [
        {"disposition": "ANSWERED", "billable_seconds": 600},   # 10 min
        {"disposition": "NO ANSWER", "billable_seconds": 0},
        {"disposition": "ANSWERED", "billable_seconds": 60},    # 1 min
    ]
    cost = compute_daily_cost(records, cost_per_minute=0.50)
    assert cost == 5.50  # 11 minutos * 0.50


def test_is_over_spending_limit_disabled_when_limit_zero_or_negative():
    records = [{"disposition": "ANSWERED", "billable_seconds": 100000}]
    assert is_over_spending_limit(records, cost_per_minute=1.0, daily_limit=0) is False
    assert is_over_spending_limit(records, cost_per_minute=1.0, daily_limit=-5) is False


def test_is_over_spending_limit_true_when_exceeded():
    records = [{"disposition": "ANSWERED", "billable_seconds": 6000}]  # 100 min
    assert is_over_spending_limit(records, cost_per_minute=1.0, daily_limit=50) is True


def test_is_over_spending_limit_false_when_under():
    records = [{"disposition": "ANSWERED", "billable_seconds": 60}]  # 1 min
    assert is_over_spending_limit(records, cost_per_minute=1.0, daily_limit=50) is False
