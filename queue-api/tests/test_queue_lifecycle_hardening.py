"""Fila AXE PABX: eventos AMI, isolamento e concorrência sem Asterisk externo."""
from concurrent.futures import ThreadPoolExecutor
import json

import pytest

from queue_state import QueueStateTracker, MAX_TRACKED_CALLS


def evt(name="QueueCallerJoin", *, queue="fila-t1", channel="PJSIP/t1-1001-0001",
        uid="1700000000.42", **other):
    return {"Event": name, "Queue": queue, "Channel": channel,
            "Uniqueid": uid, **other}


@pytest.mark.parametrize("name,counter", [
    ("QueueCallerLeave", "events_left"),
    ("QueueCallerAbandon", "events_abandoned"),
    ("AgentConnect", "events_answered"),
    ("AgentDump", "events_agent_dump"),
    ("AgentComplete", "events_agent_completed"),
])
def test_caller_is_removed_for_all_ami_queue_completion_events(name, counter):
    tracker = QueueStateTracker()
    tracker.apply_event(evt())
    tracker.apply_event(evt(name))
    assert tracker.waiting_list(tenant="t1") == []
    assert tracker.health_snapshot("t1")[counter] == 1


def test_hangup_removes_matching_uid_without_queue():
    tracker = QueueStateTracker()
    tracker.apply_event(evt())
    tracker.apply_event({"Event": "Hangup", "Channel": "PJSIP/t1-1001-0001",
                         "Uniqueid": "1700000000.42"})
    assert tracker.health_snapshot("t1")["events_hung_up"] == 1


def test_old_uniqueid_cannot_remove_reused_channel():
    tracker = QueueStateTracker()
    tracker.apply_event(evt(uid="id-1"))
    tracker.apply_event(evt(uid="id-2"))
    tracker.apply_event(evt("QueueCallerAbandon", uid="id-1"))
    assert len(tracker.waiting_list(tenant="t1")) == 1
    assert tracker.health_snapshot("t1")["events_ignored_uniqueid_mismatch"] == 1
    tracker.apply_event(evt("QueueCallerAbandon", uid="id-2"))
    assert tracker.waiting_list() == []


def test_missing_uniqueid_cannot_end_modern_identified_call():
    tracker = QueueStateTracker()
    tracker.apply_event(evt(uid="id-10"))
    tracker.apply_event(evt("QueueCallerLeave", uid=None))
    assert tracker.queue_for_channel("PJSIP/t1-1001-0001") == "fila-t1"
    tracker.apply_event({"Event": "Hangup", "Channel": "PJSIP/t1-1001-0001"})
    assert len(tracker.waiting_list()) == 1


def test_old_queue_event_never_removes_current_queue():
    tracker = QueueStateTracker()
    tracker.apply_event(evt(queue="fila-t1", uid="one"))
    tracker.apply_event(evt(queue="fila-t1-en", uid="two"))
    tracker.apply_event(evt("AgentConnect", queue="fila-t1", uid="two"))
    assert tracker.queue_for_channel("PJSIP/t1-1001-0001") == "fila-t1-en"
    assert tracker.health_snapshot("t1")["events_ignored_queue_mismatch"] == 1


def test_cross_tenant_requeue_with_missing_uid_denied():
    tracker = QueueStateTracker()
    tracker.apply_event(evt(queue="fila-t1", uid="first"))
    tracker.apply_event(evt(queue="fila-t10", uid=None))
    assert tracker.health_snapshot("t1")["events_rejected_cross_tenant_requeue"] == 1
    assert tracker.health_snapshot("t10")["tracked_waiting"] == 0
    assert tracker.queue_for_channel("PJSIP/t1-1001-0001") == "fila-t1"


def test_cross_tenant_requeue_requires_different_proven_uid():
    tracker = QueueStateTracker()
    tracker.apply_event(evt(queue="fila-t1", uid="first"))
    tracker.apply_event(evt(queue="fila-t10", uid="first"))
    assert tracker.health_snapshot("t10")["tracked_waiting"] == 0
    tracker.apply_event(evt(queue="fila-t10", uid="second"))
    assert tracker.health_snapshot("t1")["tracked_waiting"] == 0
    assert tracker.health_snapshot("t10")["tracked_waiting"] == 1


@pytest.mark.parametrize("queue", ["fila-t01", "fila-t1evil", "x-fila-t1",
                                    "fila-t1-xx", "fila-t1\r", "", None, []])
def test_unrecognized_queue_names_never_enter_ledger(queue):
    tracker = QueueStateTracker()
    tracker.apply_event(evt(queue=queue))
    assert tracker.waiting_list() == []


@pytest.mark.parametrize("uid", [["id"], {}, True, "bad\r\nInjection",
                                 "x" * 97, "bad uid"])
def test_bad_uniqueid_rejected(uid):
    tracker = QueueStateTracker()
    tracker.apply_event(evt(uid=uid))
    assert tracker.waiting_list() == []


def test_duplicate_join_does_not_reset_age_with_uniqueid():
    current = [1000.0]
    tracker = QueueStateTracker(clock=lambda: current[0])
    tracker.apply_event(evt())
    current[0] = 1019
    tracker.apply_event(evt())
    assert tracker.waiting_list()[0]["waiting_seconds"] == 19
    assert tracker.health_snapshot("t1")["events_duplicate_join"] == 1


def test_global_capacity_protects_memory_and_counts_drops():
    tracker = QueueStateTracker(max_waiting=2, max_per_queue=2)
    for idx in range(3):
        tracker.apply_event(evt(channel="CH" + str(idx), uid="uid-" + str(idx)))
    assert len(tracker.waiting_list()) == 2
    assert tracker.health_snapshot("t1")["events_rejected_capacity"] == 1


def test_per_queue_capacity_cannot_block_other_tenant():
    tracker = QueueStateTracker(max_waiting=3, max_per_queue=1)
    tracker.apply_event(evt(channel="CH1", uid="one"))
    tracker.apply_event(evt(channel="CH2", uid="two"))
    tracker.apply_event(evt(queue="fila-t10", channel="CH10", uid="three"))
    assert tracker.health_snapshot("t1")["events_rejected_queue_capacity"] == 1
    assert tracker.health_snapshot("t10")["tracked_waiting"] == 1


def test_old_items_expire_without_ghost_calls():
    clock = [1000.0]
    tracker = QueueStateTracker(max_age_seconds=10, clock=lambda: clock[0])
    tracker.apply_event(evt())
    clock[0] = 1010
    assert len(tracker.waiting_list()) == 1
    clock[0] = 1011
    assert tracker.waiting_list() == []
    assert tracker.health_snapshot("t1")["events_expired"] == 1


def test_backward_clock_cannot_expire_active_caller():
    clock = [1000.0]
    tracker = QueueStateTracker(max_age_seconds=5, clock=lambda: clock[0])
    tracker.apply_event(evt())
    clock[0] = 900.0
    assert tracker.waiting_list()[0]["waiting_seconds"] == 0
    assert tracker.health_snapshot("t1")["tracked_waiting"] == 1


def test_tenant_snapshots_are_exact_and_do_not_expose_customers():
    tracker = QueueStateTracker()
    tracker.apply_event(evt(channel="CH1", uid="uid-1",
                            CallerIDNum="PRIVATE-5555", CallerIDName="CLIENTE-X"))
    tracker.apply_event(evt(queue="fila-t10", channel="CH2", uid="uid-2",
                            CallerIDNum="PRIVATE-9999"))
    t1 = tracker.health_snapshot("t1")
    t10 = tracker.health_snapshot("t10")
    assert (t1["tracked_waiting"], t10["tracked_waiting"]) == (1, 1)
    assert t1["events_joined"] == t10["events_joined"] == 1
    assert "PRIVATE-" not in json.dumps(t1)
    assert "CH1" not in json.dumps(t1)
    assert "uid-1" not in json.dumps(t1)
    assert tracker.waiting_list(tenant="t1")[0]["channel"] == "CH1"
    assert tracker.waiting_list(tenant="t10")[0]["channel"] == "CH2"


def test_manual_remove_requires_same_queue_when_supplied():
    tracker = QueueStateTracker()
    tracker.apply_event(evt(queue="fila-t1"))
    tracker.remove("PJSIP/t1-1001-0001", queue_name="fila-t10")
    assert len(tracker.waiting_list()) == 1
    tracker.remove("PJSIP/t1-1001-0001", queue_name="fila-t1")
    assert tracker.health_snapshot("t1")["events_removed_by_pickup"] == 1


def test_invalid_clock_and_tenant_are_conservative():
    tracker = QueueStateTracker(clock=lambda: float("nan"))
    tracker.apply_event(evt())
    assert tracker.waiting_list() == []
    assert tracker.health_snapshot("t1")["longest_wait_seconds"] is None
    with pytest.raises(ValueError):
        tracker.health_snapshot("t01")
    assert tracker.waiting_list(tenant="t01") == []


@pytest.mark.parametrize("max_waiting,max_per_queue,max_age", [
    (0, 1, 10), (True, 1, 10), (MAX_TRACKED_CALLS + 1, 1, 10),
    (10, 11, 10), (10, 2, 0), (10, 2, float("inf")),
])
def test_invalid_limits_rejected(max_waiting, max_per_queue, max_age):
    with pytest.raises(ValueError):
        QueueStateTracker(max_waiting=max_waiting,
                          max_per_queue=max_per_queue, max_age_seconds=max_age)


def test_concurrent_join_and_leave_keep_consistent_ledger():
    tracker = QueueStateTracker(max_waiting=200, max_per_queue=200)
    def work(i):
        event = evt(queue="fila-t1", channel="CH" + str(i), uid="id-" + str(i))
        tracker.apply_event(event)
        if i % 2:
            tracker.apply_event(evt("QueueCallerLeave", queue="fila-t1",
                                    channel="CH" + str(i), uid="id-" + str(i)))
    with ThreadPoolExecutor(max_workers=12) as workers:
        list(workers.map(work, range(100)))
    assert tracker.health_snapshot("t1")["tracked_waiting"] == 50
    assert tracker.health_snapshot("t1")["events_left"] == 50


def test_bad_callerid_is_scrubbed_before_snapshot():
    tracker = QueueStateTracker()
    tracker.apply_event(evt(CallerIDNum=["bad"], CallerIDName="bad\r\nHTTP-Injected"))
    view = tracker.waiting_list()[0]
    assert view["caller_id_num"] == "" and view["caller_id_name"] == ""
