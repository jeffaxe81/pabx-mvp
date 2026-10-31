from fraud_detection import CallRateTracker

def test_fraud_queries_fail_closed_on_invalid_windows():
    tracker = CallRateTracker(clock=lambda:100)
    tracker.track_call("t1-1001","5511999999999")
    for window in (None, True, 0, -1, 86401, "60", 1.5):
        assert tracker.is_abnormal("t1-1001",window_seconds=window) is False
        assert tracker.recent_destinations("t1-1001",window_seconds=window) == []
    for threshold in (None, True, -1, 10001, "1"):
        assert not tracker.is_abnormal("t1-1001",threshold=threshold)
    assert tracker.is_abnormal("t1-1001",threshold=0)
