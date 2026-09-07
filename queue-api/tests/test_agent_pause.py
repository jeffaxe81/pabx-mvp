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
