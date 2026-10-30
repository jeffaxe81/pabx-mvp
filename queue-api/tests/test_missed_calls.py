from missed_calls import parse_missed_call_event, MissedCallsLog


def test_dial_end_with_noanswer_is_a_missed_call():
    event = {
        "Event": "DialEnd",
        "DialStatus": "NOANSWER",
        "CallerIDNum": "5511988887777",
        "CallerIDName": "Cliente Teste",
        "Exten": "1000",
    }
    result = parse_missed_call_event(event)
    assert result is not None
    assert result["caller_id_num"] == "5511988887777"
    assert result["reason"] == "NOANSWER"
    assert result["source"] == "dial"


def test_dial_end_with_busy_is_a_missed_call():
    event = {"Event": "DialEnd", "DialStatus": "BUSY", "CallerIDNum": "123"}
    assert parse_missed_call_event(event)["reason"] == "BUSY"


def test_dial_end_with_answer_is_not_a_missed_call():
    event = {"Event": "DialEnd", "DialStatus": "ANSWER", "CallerIDNum": "123"}
    assert parse_missed_call_event(event) is None


def test_queue_caller_abandon_is_a_missed_call():
    event = {
        "Event": "QueueCallerAbandon",
        "Queue": "fila-t1",
        "CallerIDNum": "5511999998888",
    }
    result = parse_missed_call_event(event)
    assert result is not None
    assert result["reason"] == "ABANDONED"
    assert result["source"] == "queue"
    assert result["destination"] == "fila-t1"


def test_unrelated_events_return_none():
    assert parse_missed_call_event({"Event": "PeerStatus"}) is None
    assert parse_missed_call_event({"Event": "Hangup"}) is None
    assert parse_missed_call_event({}) is None


def test_missing_caller_id_falls_back_to_placeholder():
    event = {"Event": "DialEnd", "DialStatus": "NOANSWER"}
    result = parse_missed_call_event(event)
    assert result["caller_id_num"] == "desconhecido"


def test_missed_calls_log_lists_newest_first():
    log = MissedCallsLog()
    log.append({"caller_id_num": "1", "reason": "NOANSWER", "source": "dial", "caller_id_name": "", "destination": ""})
    log.append({"caller_id_num": "2", "reason": "BUSY", "source": "dial", "caller_id_name": "", "destination": ""})

    result = log.list()
    assert [r["caller_id_num"] for r in result] == ["2", "1"]


def test_missed_calls_log_respects_max_size():
    log = MissedCallsLog(max_size=3)
    for i in range(5):
        log.append({"caller_id_num": str(i), "reason": "NOANSWER", "source": "dial", "caller_id_name": "", "destination": ""})

    assert len(log.list(limit=100)) == 3
    # os 3 mais recentes (2, 3, 4) devem ter sobrevivido
    assert {r["caller_id_num"] for r in log.list(limit=100)} == {"2", "3", "4"}


def test_missed_calls_log_respects_limit_param():
    log = MissedCallsLog()
    for i in range(10):
        log.append({"caller_id_num": str(i), "reason": "NOANSWER", "source": "dial", "caller_id_name": "", "destination": ""})

    assert len(log.list(limit=3)) == 3


def test_malformed_ami_records_are_ignored_without_type_errors():
    for source in (None, [], True, "not-event"):
        assert parse_missed_call_event(source) is None
    for status in ([], {}, None, 5):
        assert parse_missed_call_event({"Event": "DialEnd",
                                        "DialStatus": status}) is None


def test_missed_call_ami_fields_never_return_control_chars_or_objects():
    event = {"Event": "DialEnd", "DialStatus": "NOANSWER",
             "CallerIDNum": ["5511999998888"],
             "CallerIDName": "bad\\r\\nInjected: yes",
             "DestCallerIDNum": {"unsafe": "value"},
             "Exten": ["t1-1001"]}
    item = parse_missed_call_event(event)
    assert item["caller_id_num"] == "desconhecido"
    assert item["caller_id_name"] == ""
    assert item["destination"] == ""
    assert parse_missed_call_event({
        "Event": "QueueCallerAbandon", "Queue": "fila-t1\\nFake",
        "CallerIDNum": "5511999998888", "CallerIDName": "ok",
    })["destination"] == ""


def test_oversized_ami_data_does_not_enter_missed_call_history():
    event = {"Event": "QueueCallerAbandon", "Queue": "fila-t1",
             "CallerIDNum": "1" * 200, "CallerIDName": "A" * 1000}
    normalized = parse_missed_call_event(event)
    assert normalized["caller_id_num"] == "desconhecido"
    assert normalized["caller_id_name"] == ""
    assert normalized["destination"] == "fila-t1"
