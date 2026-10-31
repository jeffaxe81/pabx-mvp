import queue_sla
from queue_sla import QueueSLATracker

def test_sla_dedupe_memory_is_bounded_and_recent_ids_remain_deduped(monkeypatch):
    monkeypatch.setattr(queue_sla, "MAX_SLA_DEDUPE_IDS", 3)
    tracker = QueueSLATracker(clock=lambda: 1700000000)
    def event(uid):
        return {"Event": "AgentConnect", "Queue": "fila-t1", "HoldTime": "7", "Uniqueid": uid}
    for uid in ("1", "2", "3", "4"):
        tracker.apply_event(event(uid))
    assert len(tracker._seen_ami_calls) == 3
    assert len(tracker._seen_ami_call_order) == 3
    tracker.apply_event(event("4"))
    assert tracker.snapshot()["fila-t1"]["offered"] == 4
    tracker.apply_event(event("1"))  # Evicted IDs can be replayed: bounded retention.
    assert tracker.snapshot()["fila-t1"]["offered"] == 5
