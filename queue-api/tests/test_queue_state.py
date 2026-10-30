import time

from queue_state import QueueStateTracker


def test_join_adds_caller_to_waiting_list():
    tracker = QueueStateTracker()
    tracker.apply_event({
        "Event": "QueueCallerJoin",
        "Queue": "fila-t1",
        "Channel": "PJSIP/gateway-tdm-0001",
        "CallerIDNum": "5511988887777",
        "CallerIDName": "Cliente Teste",
    })

    waiting = tracker.waiting_list("fila-t1")
    assert len(waiting) == 1
    assert waiting[0]["channel"] == "PJSIP/gateway-tdm-0001"
    assert waiting[0]["caller_id_num"] == "5511988887777"
    assert waiting[0]["waiting_seconds"] >= 0


def test_leave_removes_caller_from_waiting_list():
    tracker = QueueStateTracker()
    tracker.apply_event({"Event": "QueueCallerJoin", "Queue": "fila-t1", "Channel": "CH1"})
    tracker.apply_event({"Event": "QueueCallerLeave", "Queue": "fila-t1", "Channel": "CH1"})

    assert tracker.waiting_list("fila-t1") == []


def test_hangup_event_also_removes_caller():
    """
    Segurança extra: se o canal cair por qualquer motivo sem gerar um
    QueueCallerLeave explícito, o Hangup ainda deve limpar o estado -
    senão uma chamada "fantasma" fica aparecendo pra sempre no painel.
    """
    tracker = QueueStateTracker()
    tracker.apply_event({"Event": "QueueCallerJoin", "Queue": "fila-t1", "Channel": "CH1"})
    tracker.apply_event({"Event": "Hangup", "Channel": "CH1"})

    assert tracker.waiting_list("fila-t1") == []


def test_waiting_list_filters_by_queue_name():
    tracker = QueueStateTracker()
    tracker.apply_event({"Event": "QueueCallerJoin", "Queue": "fila-t1", "Channel": "CH1"})
    tracker.apply_event({"Event": "QueueCallerJoin", "Queue": "fila-t2", "Channel": "CH2"})

    assert [c["channel"] for c in tracker.waiting_list("fila-t1")] == ["CH1"]
    assert [c["channel"] for c in tracker.waiting_list("fila-t2")] == ["CH2"]
    assert len(tracker.waiting_list()) == 2  # sem filtro, retorna todas


def test_waiting_list_ordered_oldest_first():
    tracker = QueueStateTracker()
    tracker.apply_event({"Event": "QueueCallerJoin", "Queue": "fila-t1", "Channel": "CH1"})
    time.sleep(0.01)
    tracker.apply_event({"Event": "QueueCallerJoin", "Queue": "fila-t1", "Channel": "CH2"})

    waiting = tracker.waiting_list("fila-t1")
    assert [c["channel"] for c in waiting] == ["CH1", "CH2"]


def test_manual_remove_after_pickup():
    tracker = QueueStateTracker()
    tracker.apply_event({"Event": "QueueCallerJoin", "Queue": "fila-t1", "Channel": "CH1"})
    tracker.remove("CH1")
    assert tracker.waiting_list("fila-t1") == []


def test_unrelated_events_are_ignored_without_crashing():
    tracker = QueueStateTracker()
    tracker.apply_event({"Event": "PeerStatus", "Peer": "PJSIP/t1-1001"})
    tracker.apply_event({"Event": "Newchannel", "Channel": "CH1"})
    assert tracker.waiting_list() == []


def test_join_without_channel_is_ignored():
    """Evento malformado (sem Channel) não deve quebrar nem poluir o estado."""
    tracker = QueueStateTracker()
    tracker.apply_event({"Event": "QueueCallerJoin", "Queue": "fila-t1"})
    assert tracker.waiting_list() == []


def test_duplicate_join_does_not_reset_wait_time(monkeypatch):
    import queue_state
    current = [100.0]
    monkeypatch.setattr(queue_state.time, "time", lambda: current[0])
    tracker = QueueStateTracker()
    event = {"Event": "QueueCallerJoin", "Queue": "fila-t1", "Channel": "CH1"}
    tracker.apply_event(event)
    current[0] = 115.0
    tracker.apply_event(event)
    assert tracker.waiting_list()[0]["waiting_seconds"] == 15


def test_late_leave_from_old_queue_cannot_remove_requeued_channel():
    tracker = QueueStateTracker()
    # Reaproveitar Channel entre tenants exige Uniqueid distinto:
    # sem esse vínculo o rastreador não permite troca ambígua.
    tracker.apply_event({"Event": "QueueCallerJoin", "Queue": "fila-t1",
                         "Channel": "CH1", "Uniqueid": "old-call"})
    tracker.apply_event({"Event": "QueueCallerJoin", "Queue": "fila-t2",
                         "Channel": "CH1", "Uniqueid": "new-call"})
    tracker.apply_event({"Event": "QueueCallerLeave", "Queue": "fila-t1",
                         "Channel": "CH1", "Uniqueid": "old-call"})
    assert tracker.queue_for_channel("CH1") == "fila-t2"
    tracker.apply_event({"Event": "QueueCallerLeave", "Queue": "fila-t2",
                         "Channel": "CH1", "Uniqueid": "new-call"})
    assert tracker.waiting_list() == []


def test_invalid_ami_channels_and_queues_are_ignored_without_pollution():
    tracker = QueueStateTracker()
    for channel, queue in (([], "fila-t1"), ({}, "fila-t1"), ("CH1", {}),
                           ("CH1", "fila-t1\r\nInjected"), ("", "fila-t1"),
                           ("CH1", ""), ("X" * 161, "fila-t1")):
        tracker.apply_event({"Event": "QueueCallerJoin", "Channel": channel,
                             "Queue": queue})
    tracker.apply_event(None)
    tracker.apply_event({"Event": "Hangup", "Channel": []})
    tracker.apply_event({"Event": "QueueCallerLeave", "Channel": {}})
    tracker.remove([])
    assert tracker.waiting_list() == []


def test_clock_rollback_never_reports_negative_wait(monkeypatch):
    import queue_state
    now = [1000.0]
    monkeypatch.setattr(queue_state.time, "time", lambda: now[0])
    tracker = QueueStateTracker()
    tracker.apply_event({"Event": "QueueCallerJoin", "Queue": "fila-t1", "Channel": "CH1"})
    now[0] = 990.0
    assert tracker.waiting_list()[0]["waiting_seconds"] == 0
    now[0] = 1015.0
    assert tracker.waiting_list()[0]["waiting_seconds"] == 15


def test_queue_caller_id_rejects_ami_objects_and_control_characters():
    tracker = QueueStateTracker()
    tracker.apply_event({"Event": "QueueCallerJoin", "Queue": "fila-t1",
                         "Channel": "CH1", "CallerIDNum": ["55119999"],
                         "CallerIDName": "nome" + chr(13) + chr(10) + "Injected"})
    item = tracker.waiting_list()[0]
    assert item["caller_id_num"] == ""
    assert item["caller_id_name"] == ""
    tracker.apply_event({"Event": "QueueCallerJoin", "Queue": "fila-t1",
                         "Channel": "CH2", "CallerIDNum": "1" * 65,
                         "CallerIDName": {"unsafe": True}})
    assert all(row["caller_id_num"] == "" and row["caller_id_name"] == ""
               for row in tracker.waiting_list())
    tracker.apply_event({"Event": "QueueCallerJoin", "Queue": "fila-t2",
                         "Channel": "CH3", "CallerIDNum": "+5511988776655",
                         "CallerIDName": "Cliente Exemplo"})
    assert tracker.waiting_list("fila-t2")[0]["caller_id_name"] == "Cliente Exemplo"
