from fraud_detection import CallRateTracker

def test_malformed_ami_fields_are_not_tracked():
    tracker = CallRateTracker(clock=lambda: 1000.0)
    for ext, dst in (([], "5511"), (True, "5511"), ("t1-1001", None), ("t1-1001", "x"*200), ("t1-1001\n", "5511")):
        tracker.track_call(ext, dst)
    assert tracker.recent_destinations("t1-1001") == []

def test_valid_call_still_tracked():
    tracker = CallRateTracker(clock=lambda: 1000.0)
    tracker.track_call("t1-1001", "5511999999999")
    assert tracker.recent_destinations("t1-1001") == ["5511999999999"]
