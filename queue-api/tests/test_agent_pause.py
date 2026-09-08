import time

from agent_pause import (
    validate_pause_request, extract_extension_from_interface,
    parse_queue_member_pause_event, AgentPauseStore,
)


# ---------- validate_pause_request ----------

def test_accepts_valid_pause_with_reason():
    ok, error, cleaned = validate_pause_request({"extension": "t1-recepcao", "paused": True, "reason": "Almoço"})
    assert ok is True
    assert cleaned == {"extension": "t1-recepcao", "paused": True, "reason": "Almoço"}


def test_accepts_unpause_without_reason():
    ok, error, cleaned = validate_pause_request({"extension": "t1-recepcao", "paused": False})
    assert ok is True
    assert cleaned["reason"] == ""


def test_rejects_pause_without_reason():
    ok, error, _ = validate_pause_request({"extension": "t1-recepcao", "paused": True})
    assert ok is False
    assert "motivo" in error


def test_rejects_missing_extension():
    ok, error, _ = validate_pause_request({"paused": True, "reason": "Almoço"})
    assert ok is False


def test_rejects_non_boolean_paused():
    ok, error, _ = validate_pause_request({"extension": "t1-recepcao", "paused": "sim", "reason": "x"})
    assert ok is False


# ---------- extract_extension_from_interface ----------

def test_extracts_extension_from_valid_interface():
    assert extract_extension_from_interface("PJSIP/t1-recepcao") == "t1-recepcao"


def test_returns_none_for_malformed_interface():
    assert extract_extension_from_interface("SIP/1010") is None
    assert extract_extension_from_interface("") is None
    assert extract_extension_from_interface(None) is None


# ---------- parse_queue_member_pause_event ----------

def test_parses_pause_event():
    event = {"Event": "QueueMemberPause", "Interface": "PJSIP/t1-recepcao", "Paused": "1", "Reason": "Almoço"}
    result = parse_queue_member_pause_event(event)
    assert result == {"extension": "t1-recepcao", "paused": True, "reason": "Almoço"}


def test_parses_unpause_event():
    event = {"Event": "QueueMemberPause", "Interface": "PJSIP/t1-recepcao", "Paused": "0"}
    result = parse_queue_member_pause_event(event)
    assert result["paused"] is False


def test_ignores_unrelated_events():
    assert parse_queue_member_pause_event({"Event": "Hangup"}) is None


def test_ignores_event_with_malformed_interface():
    event = {"Event": "QueueMemberPause", "Interface": "SIP/1010", "Paused": "1"}
    assert parse_queue_member_pause_event(event) is None


# ---------- AgentPauseStore ----------

def test_store_tracks_pause_state():
    store = AgentPauseStore()
    store.apply_event({"Event": "QueueMemberPause", "Interface": "PJSIP/t1-recepcao", "Paused": "1", "Reason": "Almoço"})
    state = store.get("t1-recepcao")
    assert state["paused"] is True
    assert state["reason"] == "Almoço"


def test_store_clears_reason_on_unpause():
    store = AgentPauseStore()
    store.apply_event({"Event": "QueueMemberPause", "Interface": "PJSIP/t1-recepcao", "Paused": "1", "Reason": "Almoço"})
    store.apply_event({"Event": "QueueMemberPause", "Interface": "PJSIP/t1-recepcao", "Paused": "0"})
    state = store.get("t1-recepcao")
    assert state["paused"] is False
    assert state["reason"] == ""


def test_store_default_state_for_unknown_extension():
    store = AgentPauseStore()
    state = store.get("nao-existe")
    assert state["paused"] is False
    assert state["since"] is None


def test_store_tracks_multiple_extensions_independently():
    store = AgentPauseStore()
    store.apply_event({"Event": "QueueMemberPause", "Interface": "PJSIP/t1-recepcao", "Paused": "1", "Reason": "Almoço"})
    store.apply_event({"Event": "QueueMemberPause", "Interface": "PJSIP/t1-recepcao-2", "Paused": "1", "Reason": "Reunião"})

    snapshot = store.snapshot()
    assert snapshot["t1-recepcao"]["reason"] == "Almoço"
    assert snapshot["t1-recepcao-2"]["reason"] == "Reunião"


def test_store_ignores_unrelated_events_without_crashing():
    store = AgentPauseStore()
    store.apply_event({"Event": "Hangup"})
    assert store.snapshot() == {}


# ---------- merge_pause_into_states ----------

def test_merge_adds_pause_reason_when_paused():
    from agent_pause import merge_pause_into_states
    states = [{"exten": "t1-recepcao", "status_label": "livre"}]
    pause_snapshot = {"t1-recepcao": {"paused": True, "reason": "Almoço", "since": 123}}

    merged = merge_pause_into_states(states, pause_snapshot)
    assert merged[0]["pause_reason"] == "Almoço"
    assert merged[0]["status_label"] == "livre"  # estado automático preservado


def test_merge_sets_none_when_not_paused():
    from agent_pause import merge_pause_into_states
    states = [{"exten": "t1-recepcao", "status_label": "livre"}]
    pause_snapshot = {"t1-recepcao": {"paused": False, "reason": "", "since": 123}}

    merged = merge_pause_into_states(states, pause_snapshot)
    assert merged[0]["pause_reason"] is None


def test_merge_handles_extension_without_any_pause_record():
    from agent_pause import merge_pause_into_states
    states = [{"exten": "t1-recepcao", "status_label": "livre"}]
    merged = merge_pause_into_states(states, {})
    assert merged[0]["pause_reason"] is None


# ---------- Histórico de pausas (backlog #57) ----------

def test_unpausing_records_complete_history_entry():
    from agent_pause import AgentPauseStore

    class FakeHistoryStore:
        def __init__(self):
            self.records = []

        def append(self, record):
            self.records.append(record)

    fake_time = [1000.0]
    history = FakeHistoryStore()
    store = AgentPauseStore(history_store=history, clock=lambda: fake_time[0])

    store.apply_event({"Event": "QueueMemberPause", "Interface": "PJSIP/t1-recepcao", "Paused": "1", "Reason": "Almoço"})
    fake_time[0] += 1800  # 30 minutos depois
    store.apply_event({"Event": "QueueMemberPause", "Interface": "PJSIP/t1-recepcao", "Paused": "0"})

    assert len(history.records) == 1
    record = history.records[0]
    assert record["extension"] == "t1-recepcao"
    assert record["reason"] == "Almoço"
    assert record["duration_seconds"] == 1800.0


def test_pausing_does_not_record_history_yet():
    """Só ao DESPAUSAR a duração é conhecida - pausar sozinho não deveria gravar nada ainda."""
    from agent_pause import AgentPauseStore

    class FakeHistoryStore:
        def __init__(self):
            self.records = []

        def append(self, record):
            self.records.append(record)

    history = FakeHistoryStore()
    store = AgentPauseStore(history_store=history)
    store.apply_event({"Event": "QueueMemberPause", "Interface": "PJSIP/t1-recepcao", "Paused": "1", "Reason": "Almoço"})

    assert history.records == []


def test_unpause_without_prior_pause_state_does_not_crash_or_record():
    """
    Primeiro evento depois do queue-api reiniciar pode ser um
    despausar sem termos visto o pausar - não tem como saber quando
    começou, então não inventa uma duração.
    """
    from agent_pause import AgentPauseStore

    class FakeHistoryStore:
        def __init__(self):
            self.records = []

        def append(self, record):
            self.records.append(record)

    history = FakeHistoryStore()
    store = AgentPauseStore(history_store=history)
    store.apply_event({"Event": "QueueMemberPause", "Interface": "PJSIP/t1-recepcao", "Paused": "0"})

    assert history.records == []


def test_store_works_without_history_store():
    """history_store é opcional - o rastreamento de estado atual continua funcionando sem ele."""
    from agent_pause import AgentPauseStore
    store = AgentPauseStore()
    store.apply_event({"Event": "QueueMemberPause", "Interface": "PJSIP/t1-recepcao", "Paused": "1", "Reason": "Almoço"})
    store.apply_event({"Event": "QueueMemberPause", "Interface": "PJSIP/t1-recepcao", "Paused": "0"})
    assert store.get("t1-recepcao")["paused"] is False


# ---------- PauseHistoryStore ----------

def test_history_store_append_and_load(tmp_path):
    from agent_pause import PauseHistoryStore
    path = tmp_path / "pause_history.jsonl"
    store = PauseHistoryStore(path)
    store.append({"extension": "t1-recepcao", "reason": "Almoço", "duration_seconds": 1800})

    records = store.load_all()
    assert len(records) == 1
    assert records[0]["reason"] == "Almoço"


def test_history_store_load_all_missing_file_returns_empty(tmp_path):
    from agent_pause import PauseHistoryStore
    store = PauseHistoryStore(tmp_path / "nao-existe.jsonl")
    assert store.load_all() == []


def test_history_store_ignores_malformed_lines(tmp_path):
    from agent_pause import PauseHistoryStore
    path = tmp_path / "pause_history.jsonl"
    path.write_text('{"extension": "t1-recepcao", "reason": "Almoço", "duration_seconds": 60}\nlinha quebrada\n', encoding="utf-8")

    store = PauseHistoryStore(path)
    records = store.load_all()
    assert len(records) == 1


# ---------- summarize_pause_time_by_reason ----------

def test_summarize_by_reason_sums_correctly():
    from agent_pause import summarize_pause_time_by_reason
    records = [
        {"extension": "t1-recepcao", "reason": "Almoço", "duration_seconds": 1800},
        {"extension": "t1-recepcao-2", "reason": "Almoço", "duration_seconds": 1200},
        {"extension": "t1-recepcao", "reason": "Banheiro", "duration_seconds": 300},
    ]
    result = summarize_pause_time_by_reason(records)
    assert result == {"Almoço": 3000.0, "Banheiro": 300.0}


def test_summarize_by_reason_empty_records():
    from agent_pause import summarize_pause_time_by_reason
    assert summarize_pause_time_by_reason([]) == {}


# ---------- summarize_pause_time_by_extension ----------

def test_summarize_by_extension_sums_and_counts():
    from agent_pause import summarize_pause_time_by_extension
    records = [
        {"extension": "t1-recepcao", "reason": "Almoço", "duration_seconds": 1800},
        {"extension": "t1-recepcao", "reason": "Banheiro", "duration_seconds": 300},
        {"extension": "t1-recepcao-2", "reason": "Almoço", "duration_seconds": 1200},
    ]
    result = summarize_pause_time_by_extension(records)
    assert result["t1-recepcao"] == {"total_seconds": 2100.0, "count": 2}
    assert result["t1-recepcao-2"] == {"total_seconds": 1200.0, "count": 1}


# ---------- filter_pause_records_by_date_range (backlog #63) ----------

def _ts(date_str):
    """Converte 'AAAA-MM-DD 12:00' num timestamp unix, meio-dia local - evita ambiguidade de fuso perto da meia-noite."""
    return time.mktime(time.strptime(f"{date_str} 12:00", "%Y-%m-%d %H:%M"))


def test_filter_by_date_range_includes_boundaries():
    from agent_pause import filter_pause_records_by_date_range
    records = [
        {"extension": "t1-recepcao", "reason": "Almoço", "started_at": _ts("2026-01-10"), "duration_seconds": 100},
        {"extension": "t1-recepcao", "reason": "Almoço", "started_at": _ts("2026-01-15"), "duration_seconds": 200},
        {"extension": "t1-recepcao", "reason": "Almoço", "started_at": _ts("2026-01-20"), "duration_seconds": 300},
    ]
    result = filter_pause_records_by_date_range(records, start="2026-01-10", end="2026-01-15")
    assert len(result) == 2
    assert all(r["duration_seconds"] in (100, 200) for r in result)


def test_filter_by_date_range_no_bounds_returns_everything():
    from agent_pause import filter_pause_records_by_date_range
    records = [{"extension": "x", "reason": "y", "started_at": _ts("2026-01-10"), "duration_seconds": 1}]
    assert filter_pause_records_by_date_range(records) == records


def test_filter_by_date_range_only_start():
    from agent_pause import filter_pause_records_by_date_range
    records = [
        {"extension": "x", "reason": "y", "started_at": _ts("2026-01-05"), "duration_seconds": 1},
        {"extension": "x", "reason": "y", "started_at": _ts("2026-01-15"), "duration_seconds": 2},
    ]
    result = filter_pause_records_by_date_range(records, start="2026-01-10")
    assert len(result) == 1
    assert result[0]["duration_seconds"] == 2


def test_filter_by_date_range_only_end():
    from agent_pause import filter_pause_records_by_date_range
    records = [
        {"extension": "x", "reason": "y", "started_at": _ts("2026-01-05"), "duration_seconds": 1},
        {"extension": "x", "reason": "y", "started_at": _ts("2026-01-15"), "duration_seconds": 2},
    ]
    result = filter_pause_records_by_date_range(records, end="2026-01-10")
    assert len(result) == 1
    assert result[0]["duration_seconds"] == 1


def test_filter_by_date_range_empty_records():
    from agent_pause import filter_pause_records_by_date_range
    assert filter_pause_records_by_date_range([], start="2026-01-01") == []
