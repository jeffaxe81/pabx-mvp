from fraud_detection import CallRateTracker


def test_rate_tracker_preserves_recent_call_detection():
    now = [1000.0]
    tracker = CallRateTracker(clock=lambda: now[0])
    for _ in range(11):
        tracker.track_call("t1-1001", "11999998888")
    assert tracker.is_abnormal("t1-1001")


def test_rate_tracker_prunes_old_calls():
    now = [1000.0]
    tracker = CallRateTracker(clock=lambda: now[0])
    tracker.track_call("1001", "11111111")
    now[0] += 86401
    tracker.track_call("1001", "22222222")
    assert tracker._calls["1001"] == [(now[0], "22222222")]


def test_tracker_bounds_high_volume():
    tracker = CallRateTracker(clock=lambda: 1000.0)
    for _ in range(10005):
        tracker.track_call("1001", "11999998888")
    assert len(tracker._calls["1001"]) == 10000
