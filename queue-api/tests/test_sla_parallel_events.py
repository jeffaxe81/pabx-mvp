"""SLA em API + AMI concorrentes: dedupe e rollover não podem competir."""
from concurrent.futures import ThreadPoolExecutor

from queue_sla import QueueSLATracker


def event(queue, uniqueid, wait=10):
    return {"Event": "AgentConnect", "Queue": queue,
            "Uniqueid": uniqueid, "HoldTime": str(wait)}


def test_ami_redelivery_is_idempotent_with_simultaneous_http_snapshots():
    tracker = QueueSLATracker(threshold_seconds=20)
    duplicated = event("fila-t1", "1792670400.1")
    distinct = [event("fila-t1", f"1792670400.{100 + i}")
                for i in range(120)]
    work = [duplicated] * 240 + distinct + [
        event("fila-t10", "1792670400.1", 30)
    ] * 60

    def run(index):
        if index % 7 == 0:
            snapshot = tracker.snapshot()
            for stats in snapshot.values():
                assert 0 <= stats["within_sla"] <= stats["offered"]
                assert 0 <= stats["sla_percent"] <= 100
        tracker.apply_event(work[index])
    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(run, range(len(work))))

    assert tracker.snapshot() == {
        "fila-t1": {"offered": 121, "within_sla": 121, "sla_percent": 100.0},
        "fila-t10": {"offered": 1, "within_sla": 0, "sla_percent": 0.0},
    }


def test_daily_rollover_persists_once_with_concurrent_ami_delivery():
    class Store:
        def __init__(self):
            self.rows = []
        def append(self, row):
            self.rows.append(dict(row))

    clock = [1_000_000.0]
    store = Store()
    tracker = QueueSLATracker(
        threshold_seconds=20, clock=lambda: clock[0], history_store=store
    )
    prior = event("fila-t2", "1792670400.22")
    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(tracker.apply_event, [prior] * 220))
    assert tracker.snapshot()["fila-t2"]["offered"] == 1
    clock[0] += 90_000
    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(lambda _: tracker.snapshot(), range(90)))
    assert len(store.rows) == 1
    assert store.rows[0]["queue"] == "fila-t2"
    assert store.rows[0]["offered"] == 1
    assert store.rows[0]["within_sla"] == 1
    assert tracker.snapshot() == {}
