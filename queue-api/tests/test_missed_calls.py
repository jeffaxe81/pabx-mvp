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
             "CallerIDName": "bad\r\nInjected: yes",
             "DestCallerIDNum": {"unsafe": "value"},
             "Exten": ["t1-1001"]}
    item = parse_missed_call_event(event)
    assert item["caller_id_num"] == "desconhecido"
    assert item["caller_id_name"] == ""
    assert item["destination"] == ""
    assert parse_missed_call_event({
        "Event": "QueueCallerAbandon", "Queue": "fila-t1\nFake",
        "CallerIDNum": "5511999998888", "CallerIDName": "ok",
    })["destination"] == ""


def test_oversized_ami_data_does_not_enter_missed_call_history():
    event = {"Event": "QueueCallerAbandon", "Queue": "fila-t1",
             "CallerIDNum": "1" * 200, "CallerIDName": "A" * 1000}
    normalized = parse_missed_call_event(event)
    assert normalized["caller_id_num"] == "desconhecido"
    assert normalized["caller_id_name"] == ""
    assert normalized["destination"] == "fila-t1"


def test_missed_calls_log_ignores_non_object_ami_data():
    log = MissedCallsLog()
    for raw in (None, [], False, "missed"):
        assert log.append(raw) is False
    assert log.list() == []
    log.append({"caller_id_num": "123", "reason": "NOANSWER"})
    assert len(log.list()) == 1

# Programa 30 frentes — chamadas perdidas: cinco garantias de histórico.
def test_30_missed_rejects_invalid_history_capacity():
    import pytest
    for capacity in (0, -1, True, 1.2, None, "100", 10001):
        with pytest.raises(ValueError):
            MissedCallsLog(max_size=capacity)


def test_30_missed_ignores_invalid_records_without_crashing():
    log = MissedCallsLog()
    for value in (None, [], True, "NOT DICT"):
        assert log.append(value) is False
    assert log.list() == []


def test_30_missed_sanitizes_direct_inserts_without_control_chars():
    log = MissedCallsLog()
    log.append({"caller_id_num": ["1"], "caller_id_name": "x" + chr(10) + "Forged",
                "destination": {"x": "y"}, "reason": "BUSY", "source": "dial"})
    row = log.list()[0]
    assert row["caller_id_num"] == "desconhecido"
    assert row["caller_id_name"] == ""
    assert row["destination"] == ""


def test_30_missed_invalid_limit_returns_empty_instead_of_all():
    log = MissedCallsLog()
    log.append({"caller_id_num": "1"})
    for limit in (None, True, 0, -1, 1.5, "10", {}):
        assert log.list(limit=limit) == []
    assert len(log.list(limit=9999)) == 1


def test_30_missed_list_returns_detached_copy_and_true_timestamp():
    log = MissedCallsLog(max_size=2)
    original = {"caller_id_num": "123", "timestamp": 0}
    assert log.append(original) is True
    copy = log.list()[0]
    assert copy["timestamp"] > 0
    assert original["timestamp"] == 0
    copy["caller_id_num"] = "changed"
    assert log.list()[0]["caller_id_num"] == "123"
    log.append({"caller_id_num": "second"})
    log.append({"caller_id_num": "third"})
    assert [x["caller_id_num"] for x in log.list()] == ["third", "second"]


def test_log_does_not_persist_unexpected_nested_or_sensitive_fields():
    log = MissedCallsLog()
    inserted = {"caller_id_num": "123", "reason": "BUSY",
                "tenant_token": "nao-registrar",
                "nested": {"secret": ["nunca", "persistir"]},
                "source": "dial", "destination": "1000"}
    assert log.append(inserted) is True
    row = log.list()[0]
    assert set(row) == {"caller_id_num", "reason", "source", "destination", "timestamp"}
    assert "nao-registrar" not in str(row)
    assert "nunca" not in str(row)


def test_log_sanitizes_known_fields_without_mutating_caller_input():
    log = MissedCallsLog()
    raw = {"caller_id_num": "12\nHeader: malicious", "source": {"unexpected": True}}
    assert log.append(raw) is True
    assert log.list()[0]["caller_id_num"] == "desconhecido"
    assert log.list()[0]["source"] == ""
    assert raw["source"] == {"unexpected": True}
