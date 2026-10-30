from queue_sla import parse_agent_connect_event, parse_queue_caller_abandon_event

def test_unrealistic_holdtime_never_counts_as_zero():
    e = {"Event": "AgentConnect", "Queue": "fila-t1", "HoldTime": "86401"}
    assert parse_agent_connect_event(e)["hold_time"] is None
    e2 = {"Event": "QueueCallerAbandon", "Queue": "fila-t1", "HoldTime": 99999999}
    assert parse_queue_caller_abandon_event(e2)["hold_time"] is None

def test_regular_holdtime_keeps_contract():
    assert parse_agent_connect_event({"Event": "AgentConnect", "Queue": "fila-t1", "HoldTime": "20"})["hold_time"] == 20
