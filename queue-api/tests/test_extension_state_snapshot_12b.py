from extension_states import ExtensionStateTracker

def test_snapshot_consumer_cannot_mutate_ami_tracker():
    s = ExtensionStateTracker()
    s.apply_event({"Event":"ExtensionStatus","Exten":"t1-1001","Context":"t1-hints","Status":"0"})
    view = s.snapshot()
    view[0]["status_label"] = "forjado"
    view[0]["exten"] = "t2-1001"
    assert s.snapshot()[0]["status_label"] == "livre"
    assert s.snapshot()[0]["exten"] == "t1-1001"
