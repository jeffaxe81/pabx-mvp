import fraud_detection
from fraud_detection import CallRateTracker

def test_fraud_tracker_rejects_over_capacity_without_losing_existing(monkeypatch):
    monkeypatch.setattr(fraud_detection,"MAX_RATE_TRACKED_EXTENSIONS",2)
    tracker=CallRateTracker(clock=lambda:1000)
    tracker.track_call("t1-1001","11911112222")
    tracker.track_call("t1-1002","11911113333")
    tracker.track_call("t1-1003","11911114444")
    assert set(tracker._calls)=={"t1-1001","t1-1002"}
    tracker.track_call("t1-1001","11911115555")
    assert len(tracker._calls["t1-1001"])==2

def test_fraud_tracker_ignores_nonfinite_clock():
    tracker=CallRateTracker(clock=lambda:float("nan"))
    tracker.track_call("t1-1001","11911112222")
    assert tracker._calls=={}
