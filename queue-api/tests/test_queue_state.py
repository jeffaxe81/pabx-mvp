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
