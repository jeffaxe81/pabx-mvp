from extension_states import ExtensionStateTracker


def test_applies_extension_status_event():
    tracker = ExtensionStateTracker()
    tracker.apply_event({"Event": "ExtensionStatus", "Exten": "1010", "Context": "t1-hints", "Status": "0"})

    snapshot = tracker.snapshot()
    assert len(snapshot) == 1
    assert snapshot[0]["exten"] == "1010"
    assert snapshot[0]["status_label"] == "livre"


def test_updates_existing_extension_on_new_event():
    tracker = ExtensionStateTracker()
    tracker.apply_event({"Event": "ExtensionStatus", "Exten": "1010", "Status": "0"})
    tracker.apply_event({"Event": "ExtensionStatus", "Exten": "1010", "Status": "1"})

    snapshot = tracker.snapshot()
    assert len(snapshot) == 1
    assert snapshot[0]["status_label"] == "em uso"


def test_unknown_status_code_falls_back_gracefully():
    tracker = ExtensionStateTracker()
    tracker.apply_event({"Event": "ExtensionStatus", "Exten": "1010", "Status": "999"})
    assert tracker.snapshot()[0]["status_label"] == "desconhecido"


def test_ignores_events_without_exten():
    tracker = ExtensionStateTracker()
    tracker.apply_event({"Event": "ExtensionStatus", "Status": "0"})
    assert tracker.snapshot() == []


def test_ignores_unrelated_events():
    tracker = ExtensionStateTracker()
    tracker.apply_event({"Event": "Hangup"})
    tracker.apply_event({"Event": "QueueCallerJoin"})
    assert tracker.snapshot() == []


def test_snapshot_sorted_by_extension_number():
    tracker = ExtensionStateTracker()
    tracker.apply_event({"Event": "ExtensionStatus", "Exten": "1011", "Status": "0"})
    tracker.apply_event({"Event": "ExtensionStatus", "Exten": "1000", "Status": "0"})
    tracker.apply_event({"Event": "ExtensionStatus", "Exten": "1010", "Status": "0"})

    assert [s["exten"] for s in tracker.snapshot()] == ["1000", "1010", "1011"]


def test_multiple_extensions_tracked_independently():
    tracker = ExtensionStateTracker()
    tracker.apply_event({"Event": "ExtensionStatus", "Exten": "1010", "Status": "0"})
    tracker.apply_event({"Event": "ExtensionStatus", "Exten": "1011", "Status": "8"})

    snapshot = {s["exten"]: s["status_label"] for s in tracker.snapshot()}
    assert snapshot == {"1010": "livre", "1011": "tocando"}
