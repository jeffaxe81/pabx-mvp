from extension_states import ExtensionStateTracker

def test_ami_extension_ids_with_spaces_are_ignored():
    tracker = ExtensionStateTracker()
    for name in ("1001 1002", " 1001", "1001 "):
        tracker.apply_event({"Event": "ExtensionStatus", "Exten": name, "Context": "t1-hints", "Status": "0"})
    assert tracker.snapshot() == []
    tracker.apply_event({"Event": "ExtensionStatus", "Exten": "t1-1001", "Context": "t1-hints", "Status": "8"})
    assert tracker.snapshot()[0]["status_label"] == "tocando"
