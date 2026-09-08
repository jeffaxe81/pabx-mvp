from queue_sla import (
    parse_agent_connect_event, parse_queue_caller_abandon_event, QueueSLATracker,
)


# ---------- parse_agent_connect_event ----------

def test_parses_agent_connect_event():
    event = {"Event": "AgentConnect", "Queue": "fila-t1", "HoldTime": "12"}
    result = parse_agent_connect_event(event)
    assert result == {"queue": "fila-t1", "hold_time": 12, "outcome": "answered"}


def test_agent_connect_handles_missing_hold_time():
    event = {"Event": "AgentConnect", "Queue": "fila-t1"}
    result = parse_agent_connect_event(event)
    assert result["hold_time"] == 0


def test_ignores_unrelated_events_for_agent_connect():
    assert parse_agent_connect_event({"Event": "Hangup"}) is None


# ---------- parse_queue_caller_abandon_event ----------

def test_parses_abandon_event():
    event = {"Event": "QueueCallerAbandon", "Queue": "fila-t1", "HoldTime": "35"}
    result = parse_queue_caller_abandon_event(event)
    assert result == {"queue": "fila-t1", "hold_time": 35, "outcome": "abandoned"}


def test_ignores_unrelated_events_for_abandon():
    assert parse_queue_caller_abandon_event({"Event": "Hangup"}) is None


# ---------- QueueSLATracker ----------

def test_call_answered_within_threshold_counts_toward_sla():
    tracker = QueueSLATracker(threshold_seconds=20)
    tracker.apply_event({"Event": "AgentConnect", "Queue": "fila-t1", "HoldTime": "10"})
    snapshot = tracker.snapshot()
    assert snapshot["fila-t1"] == {"offered": 1, "within_sla": 1, "sla_percent": 100.0}


def test_call_answered_after_threshold_does_not_count_toward_sla():
    """Foi atendida, mas tarde demais - conta no total oferecido, não no SLA."""
    tracker = QueueSLATracker(threshold_seconds=20)
    tracker.apply_event({"Event": "AgentConnect", "Queue": "fila-t1", "HoldTime": "45"})
    snapshot = tracker.snapshot()
    assert snapshot["fila-t1"] == {"offered": 1, "within_sla": 0, "sla_percent": 0.0}


def test_abandoned_call_counts_against_sla():
    """
    Cliente desistiu antes de ser atendido - conta no total oferecido
    (a fila recebeu a chamada), mas nunca dentro do SLA (nunca foi
    atendida de fato).
    """
    tracker = QueueSLATracker(threshold_seconds=20)
    tracker.apply_event({"Event": "QueueCallerAbandon", "Queue": "fila-t1", "HoldTime": "5"})
    snapshot = tracker.snapshot()
    assert snapshot["fila-t1"] == {"offered": 1, "within_sla": 0, "sla_percent": 0.0}


def test_sla_percent_is_computed_across_multiple_calls():
    tracker = QueueSLATracker(threshold_seconds=20)
    tracker.apply_event({"Event": "AgentConnect", "Queue": "fila-t1", "HoldTime": "10"})  # dentro
    tracker.apply_event({"Event": "AgentConnect", "Queue": "fila-t1", "HoldTime": "10"})  # dentro
    tracker.apply_event({"Event": "AgentConnect", "Queue": "fila-t1", "HoldTime": "30"})  # fora
    tracker.apply_event({"Event": "QueueCallerAbandon", "Queue": "fila-t1", "HoldTime": "60"})  # fora (abandono)

    snapshot = tracker.snapshot()
    assert snapshot["fila-t1"]["offered"] == 4
    assert snapshot["fila-t1"]["within_sla"] == 2
    assert snapshot["fila-t1"]["sla_percent"] == 50.0


def test_queues_tracked_independently():
    tracker = QueueSLATracker(threshold_seconds=20)
    tracker.apply_event({"Event": "AgentConnect", "Queue": "fila-t1", "HoldTime": "5"})
    tracker.apply_event({"Event": "AgentConnect", "Queue": "fila-t2", "HoldTime": "50"})

    snapshot = tracker.snapshot()
    assert snapshot["fila-t1"]["sla_percent"] == 100.0
    assert snapshot["fila-t2"]["sla_percent"] == 0.0


def test_queue_with_no_calls_does_not_appear_in_snapshot():
    tracker = QueueSLATracker()
    assert tracker.snapshot() == {}


def test_call_exactly_at_threshold_counts_within_sla():
    """Limite inclusivo - exatamente no tempo-alvo ainda é considerado dentro do SLA."""
    tracker = QueueSLATracker(threshold_seconds=20)
    tracker.apply_event({"Event": "AgentConnect", "Queue": "fila-t1", "HoldTime": "20"})
    snapshot = tracker.snapshot()
    assert snapshot["fila-t1"]["within_sla"] == 1


def test_resets_at_midnight():
    fake_time = [1000000.0]  # segunda 1970, horário qualquer
    tracker = QueueSLATracker(threshold_seconds=20, clock=lambda: fake_time[0])
    tracker.apply_event({"Event": "AgentConnect", "Queue": "fila-t1", "HoldTime": "5"})
    assert tracker.snapshot()["fila-t1"]["offered"] == 1

    fake_time[0] += 90000  # mais de 24h depois
    assert tracker.snapshot() == {}


def test_ignores_unrelated_events_without_crashing():
    tracker = QueueSLATracker()
    tracker.apply_event({"Event": "Hangup"})
    assert tracker.snapshot() == {}
