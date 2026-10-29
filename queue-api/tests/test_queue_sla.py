from queue_sla import (
    parse_agent_connect_event, parse_queue_caller_abandon_event, QueueSLATracker,
    SLAHistoryStore, summarize_sla_history_by_date, filter_sla_history_by_date_range,
)


# ---------- parse_agent_connect_event ----------

def test_parses_agent_connect_event():
    event = {"Event": "AgentConnect", "Queue": "fila-t1", "HoldTime": "12"}
    result = parse_agent_connect_event(event)
    assert result == {"queue": "fila-t1", "hold_time": 12, "outcome": "answered"}


def test_agent_connect_handles_missing_hold_time():
    event = {"Event": "AgentConnect", "Queue": "fila-t1"}
    result = parse_agent_connect_event(event)
    assert result["hold_time"] is None


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


# ---------- Histórico de SLA (backlog #58) ----------

def test_midnight_reset_persists_previous_day_summary():
    class FakeHistoryStore:
        def __init__(self):
            self.records = []

        def append(self, record):
            self.records.append(record)

    history = FakeHistoryStore()
    fake_time = [1000000.0]
    tracker = QueueSLATracker(threshold_seconds=20, clock=lambda: fake_time[0], history_store=history)

    tracker.apply_event({"Event": "AgentConnect", "Queue": "fila-t1", "HoldTime": "10"})
    tracker.apply_event({"Event": "AgentConnect", "Queue": "fila-t1", "HoldTime": "30"})

    fake_time[0] += 90000  # mais de 24h depois - vira o dia
    tracker.snapshot()  # snapshot() também dispara _reset_if_new_day()

    assert len(history.records) == 1
    record = history.records[0]
    assert record["queue"] == "fila-t1"
    assert record["offered"] == 2
    assert record["within_sla"] == 1
    assert record["sla_percent"] == 50.0
    assert "date" in record


def test_first_day_never_persists_anything():
    """Não há "dia anterior" na primeiríssima execução - nada pra persistir ainda."""
    class FakeHistoryStore:
        def __init__(self):
            self.records = []

        def append(self, record):
            self.records.append(record)

    history = FakeHistoryStore()
    tracker = QueueSLATracker(history_store=history)
    tracker.apply_event({"Event": "AgentConnect", "Queue": "fila-t1", "HoldTime": "10"})

    assert history.records == []


def test_queue_with_no_calls_is_not_persisted_on_reset():
    """Fila sem nenhuma chamada oferecida no dia não gera registro vazio no histórico."""
    class FakeHistoryStore:
        def __init__(self):
            self.records = []

        def append(self, record):
            self.records.append(record)

    history = FakeHistoryStore()
    fake_time = [1000000.0]
    tracker = QueueSLATracker(clock=lambda: fake_time[0], history_store=history)
    tracker.apply_event({"Event": "AgentConnect", "Queue": "fila-t1", "HoldTime": "10"})

    fake_time[0] += 90000
    tracker.snapshot()

    assert all(r["queue"] != "fila-t2" for r in history.records)


def test_tracker_works_without_history_store():
    """history_store é opcional - o rastreamento do dia atual continua funcionando sem ele."""
    fake_time = [1000000.0]
    tracker = QueueSLATracker(clock=lambda: fake_time[0])
    tracker.apply_event({"Event": "AgentConnect", "Queue": "fila-t1", "HoldTime": "10"})
    fake_time[0] += 90000
    assert tracker.snapshot() == {}  # virou o dia, resetou normalmente


# ---------- SLAHistoryStore ----------

def test_sla_history_store_append_and_load(tmp_path):
    path = tmp_path / "sla_history.jsonl"
    store = SLAHistoryStore(path)
    store.append({"date": "2026-01-01", "queue": "fila-t1", "offered": 10, "within_sla": 8, "sla_percent": 80.0})

    records = store.load_all()
    assert len(records) == 1
    assert records[0]["queue"] == "fila-t1"


def test_sla_history_store_missing_file_returns_empty(tmp_path):
    store = SLAHistoryStore(tmp_path / "nao-existe.jsonl")
    assert store.load_all() == []


def test_sla_history_store_ignores_malformed_lines(tmp_path):
    path = tmp_path / "sla_history.jsonl"
    path.write_text('{"date": "2026-01-01", "queue": "fila-t1", "offered": 1, "within_sla": 1, "sla_percent": 100.0}\nlixo\n', encoding="utf-8")
    store = SLAHistoryStore(path)
    assert len(store.load_all()) == 1


# ---------- summarize_sla_history_by_date ----------

def test_summarize_by_date_groups_correctly():
    records = [
        {"date": "2026-01-01", "queue": "fila-t1", "offered": 10, "within_sla": 8, "sla_percent": 80.0},
        {"date": "2026-01-01", "queue": "fila-t2", "offered": 5, "within_sla": 5, "sla_percent": 100.0},
        {"date": "2026-01-02", "queue": "fila-t1", "offered": 20, "within_sla": 10, "sla_percent": 50.0},
    ]
    result = summarize_sla_history_by_date(records)
    assert set(result.keys()) == {"2026-01-01", "2026-01-02"}
    assert result["2026-01-01"]["fila-t1"]["sla_percent"] == 80.0
    assert result["2026-01-01"]["fila-t2"]["sla_percent"] == 100.0
    assert result["2026-01-02"]["fila-t1"]["offered"] == 20


def test_summarize_by_date_empty_records():
    assert summarize_sla_history_by_date([]) == {}


# ---------- filter_sla_history_by_date_range (backlog #63) ----------

def test_filter_sla_history_includes_boundaries():
    records = [
        {"date": "2026-01-10", "queue": "fila-t1", "offered": 10, "within_sla": 8, "sla_percent": 80.0},
        {"date": "2026-01-15", "queue": "fila-t1", "offered": 10, "within_sla": 5, "sla_percent": 50.0},
        {"date": "2026-01-20", "queue": "fila-t1", "offered": 10, "within_sla": 9, "sla_percent": 90.0},
    ]
    result = filter_sla_history_by_date_range(records, start="2026-01-10", end="2026-01-15")
    assert len(result) == 2
    assert all(r["date"] in ("2026-01-10", "2026-01-15") for r in result)


def test_filter_sla_history_no_bounds_returns_everything():
    records = [{"date": "2026-01-10", "queue": "fila-t1", "offered": 1, "within_sla": 1, "sla_percent": 100.0}]
    assert filter_sla_history_by_date_range(records) == records


def test_filter_sla_history_only_start():
    records = [
        {"date": "2026-01-05", "queue": "fila-t1", "offered": 1, "within_sla": 1, "sla_percent": 100.0},
        {"date": "2026-01-15", "queue": "fila-t1", "offered": 1, "within_sla": 1, "sla_percent": 100.0},
    ]
    result = filter_sla_history_by_date_range(records, start="2026-01-10")
    assert len(result) == 1
    assert result[0]["date"] == "2026-01-15"


def test_filter_sla_history_only_end():
    records = [
        {"date": "2026-01-05", "queue": "fila-t1", "offered": 1, "within_sla": 1, "sla_percent": 100.0},
        {"date": "2026-01-15", "queue": "fila-t1", "offered": 1, "within_sla": 1, "sla_percent": 100.0},
    ]
    result = filter_sla_history_by_date_range(records, end="2026-01-10")
    assert len(result) == 1
    assert result[0]["date"] == "2026-01-05"


def test_filter_sla_history_empty_records():
    assert filter_sla_history_by_date_range([], start="2026-01-01") == []


# Marco 9 — eventos AMI incompletos não podem inflar o SLA.
import pytest


@pytest.mark.parametrize("bad", [
    None, "", "abc", "NaN", "-1", "-0.5", "3.5", "9999999999",
    -1, -0.1, 1.5, float("nan"), float("inf"), True, False, [], {},
])
def test_invalid_hold_time_counts_as_offered_but_never_achieves_sla(bad):
    tracker = QueueSLATracker(threshold_seconds=20)
    tracker.apply_event({"Event": "AgentConnect", "Queue": "fila-t10",
                         "HoldTime": bad})
    result = tracker.snapshot()
    assert result == {"fila-t10": {
        "offered": 1, "within_sla": 0, "sla_percent": 0.0,
    }}


def test_missing_hold_time_does_not_improve_real_queue_sla():
    tracker = QueueSLATracker(threshold_seconds=20)
    tracker.apply_event({"Event": "AgentConnect", "Queue": "fila-t1",
                         "HoldTime": "10"})
    tracker.apply_event({"Event": "AgentConnect", "Queue": "fila-t1"})
    tracker.apply_event({"Event": "AgentConnect", "Queue": "fila-t1",
                         "HoldTime": "80"})
    assert tracker.snapshot()["fila-t1"] == {
        "offered": 3, "within_sla": 1, "sla_percent": 33.3,
    }


def test_exact_ami_seconds_boundary_and_tenant_isolation():
    tracker = QueueSLATracker(threshold_seconds=20)
    for queue, wait in [("fila-t1", "20"), ("fila-t10", "21"),
                        ("fila-t2", "00020")]:
        tracker.apply_event({"Event": "AgentConnect", "Queue": queue,
                             "HoldTime": wait})
    assert tracker.snapshot()["fila-t1"]["sla_percent"] == 100.0
    assert tracker.snapshot()["fila-t10"]["sla_percent"] == 0.0
    assert tracker.snapshot()["fila-t2"]["sla_percent"] == 100.0


def test_invalid_abandon_still_counts_against_sla_without_crash():
    tracker = QueueSLATracker()
    tracker.apply_event({"Event": "QueueCallerAbandon", "Queue": "fila-t1",
                         "HoldTime": {}})
    assert tracker.snapshot()["fila-t1"] == {
        "offered": 1, "within_sla": 0, "sla_percent": 0.0,
    }


@pytest.mark.parametrize("event", [None, 1, [], "AgentConnect", False])
def test_non_dict_ami_event_is_ignored(event):
    tracker = QueueSLATracker()
    tracker.apply_event(event)
    assert tracker.snapshot() == {}

def test_sla_ignores_malformed_queue_identities_without_crashing():
    tracker = QueueSLATracker()
    for invalid in (None, [], {}, 123, False, "", " " * 3,
                    "fila-t1\nInjected", "fila-t1\tbad", "x" * 97):
        for event in ("AgentConnect", "QueueCallerAbandon"):
            payload = {"Event": event, "Queue": invalid, "HoldTime": "1"}
            assert (parse_agent_connect_event(payload) if event == "AgentConnect"
                    else parse_queue_caller_abandon_event(payload)) is None
            tracker.apply_event(payload)
    assert tracker.snapshot() == {}
    tracker.apply_event({"Event": "AgentConnect", "Queue": "fila-t10",
                         "HoldTime": "10"})
    assert tracker.snapshot() == {
        "fila-t10": {"offered": 1, "within_sla": 1, "sla_percent": 100.0}
    }




def test_duplicate_ami_uniqueid_counts_once_within_queue():
    tracker = QueueSLATracker(threshold_seconds=20)
    event = {"Event": "AgentConnect", "Queue": "fila-t1",
             "HoldTime": "15", "Uniqueid": "1782000000.42"}
    tracker.apply_event(event)
    tracker.apply_event(dict(event))
    assert tracker.snapshot()["fila-t1"] == {
        "offered": 1, "within_sla": 1, "sla_percent": 100.0,
    }


def test_same_uniqueid_remains_independent_across_tenants():
    tracker = QueueSLATracker(threshold_seconds=20)
    for queue, hold in (("fila-t1", "10"), ("fila-t10", "30")):
        tracker.apply_event({"Event": "AgentConnect", "Queue": queue,
                             "HoldTime": hold, "Uniqueid": "1782000000.42"})
    assert tracker.snapshot()["fila-t1"]["sla_percent"] == 100.0
    assert tracker.snapshot()["fila-t10"]["sla_percent"] == 0.0


def test_mixed_ami_final_events_with_same_uniqueid_not_double_counted():
    tracker = QueueSLATracker()
    tracker.apply_event({"Event": "QueueCallerAbandon", "Queue": "fila-t2",
                         "Uniqueid": "1782000000.99", "HoldTime": "4"})
    tracker.apply_event({"Event": "AgentConnect", "Queue": "fila-t2",
                         "Uniqueid": "1782000000.99", "HoldTime": "4"})
    assert tracker.snapshot()["fila-t2"] == {
        "offered": 1, "within_sla": 0, "sla_percent": 0.0,
    }


def test_distinct_uniqueids_count_as_distinct_calls():
    tracker = QueueSLATracker()
    for uniqueid in ("1782000000.10", "1782000000.11"):
        tracker.apply_event({"Event": "AgentConnect", "Queue": "fila-t1",
                             "Uniqueid": uniqueid, "HoldTime": "5"})
    assert tracker.snapshot()["fila-t1"]["offered"] == 2


def test_ami_uniqueid_scope_resets_on_new_day():
    clock = [1000000.0]
    tracker = QueueSLATracker(clock=lambda: clock[0])
    event = {"Event": "AgentConnect", "Queue": "fila-t1",
             "Uniqueid": "1782000000.10", "HoldTime": "2"}
    tracker.apply_event(event)
    tracker.apply_event(event)
    assert tracker.snapshot()["fila-t1"]["offered"] == 1
    clock[0] += 90000
    tracker.apply_event(event)
    assert tracker.snapshot()["fila-t1"]["offered"] == 1


@pytest.mark.parametrize("bad", [None, 123, False, [], {},
                                  "", "bad id", "call\\nInjected",
                                  "A" * 97, "a/../b"])
def test_invalid_present_ami_uniqueid_is_not_counted(bad):
    tracker = QueueSLATracker()
    event = {"Event": "AgentConnect", "Queue": "fila-t1",
             "HoldTime": "1", "Uniqueid": bad}
    if bad is None:
        # None equivale a ausência no protocolo legado.
        tracker.apply_event(event)
        assert tracker.snapshot()["fila-t1"]["offered"] == 1
    else:
        tracker.apply_event(event)
        assert tracker.snapshot() == {}


def test_ami_events_without_uniqueid_remain_supported():
    tracker = QueueSLATracker()
    for _ in range(2):
        tracker.apply_event({"Event": "AgentConnect", "Queue": "fila-t1",
                             "HoldTime": "2"})
    assert tracker.snapshot()["fila-t1"]["offered"] == 2
