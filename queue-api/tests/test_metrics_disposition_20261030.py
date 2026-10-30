from metrics import DailyMetrics

def test_unknown_cdr_status_not_mistaken_for_missed_call():
    m = DailyMetrics(clock=lambda: 1700000000)
    m.apply_cdr_event({"Event": "Cdr", "Disposition": "UNKNOWN_STATUS"})
    assert m.snapshot()["total_calls"] == 0
    assert m.snapshot()["missed_calls"] == 0

def test_known_cdr_statuses_keep_contract():
    m = DailyMetrics(clock=lambda: 1700000000)
    m.apply_cdr_event({"Event": "Cdr", "Disposition": "BUSY"})
    assert m.snapshot()["missed_calls"] == 1
