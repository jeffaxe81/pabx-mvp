from callbacks import (
    parse_callback_request_event, add_callback_request, load_callbacks,
    find_callback, next_pending_callback, mark_callback_calling,
    mark_callback_result, extract_dialed_number,
)


# ---------- parse_callback_request_event ----------

def test_parses_valid_callback_request():
    event = {"Event": "UserEvent", "UserEvent": "CallbackRequest", "CallerIDNum": "5511999998888", "CallerIDName": "Cliente"}
    result = parse_callback_request_event(event)
    assert result["caller_id_num"] == "5511999998888"
    assert result["caller_id_name"] == "Cliente"


def test_ignores_unrelated_events():
    assert parse_callback_request_event({"Event": "Hangup"}) is None
    assert parse_callback_request_event({"Event": "UserEvent", "UserEvent": "QualityStats"}) is None


def test_ignores_request_without_caller_id():
    assert parse_callback_request_event({"Event": "UserEvent", "UserEvent": "CallbackRequest"}) is None


# ---------- add_callback_request / persistência ----------

def test_add_callback_request_persists(tmp_path):
    path = tmp_path / "callbacks.json"
    entry = add_callback_request(path, "5511999998888", "Cliente Teste")

    assert entry["status"] == "pendente"
    assert entry["attempts"] == 0
    assert find_callback(load_callbacks(path), entry["id"]) is not None


# ---------- next_pending_callback (FIFO) ----------

def test_next_pending_callback_returns_oldest_first():
    callbacks = [
        {"id": "b", "status": "pendente", "requested_at": 200},
        {"id": "a", "status": "pendente", "requested_at": 100},
    ]
    assert next_pending_callback(callbacks)["id"] == "a"


def test_next_pending_callback_ignores_non_pending():
    callbacks = [{"id": "a", "status": "concluido", "requested_at": 100}]
    assert next_pending_callback(callbacks) is None


def test_next_pending_callback_empty_list():
    assert next_pending_callback([]) is None


# ---------- mark_callback_calling / mark_callback_result ----------

def test_mark_callback_calling_increments_attempts(tmp_path):
    path = tmp_path / "callbacks.json"
    entry = add_callback_request(path, "5511999998888")

    ok, error = mark_callback_calling(path, entry["id"])
    assert ok is True

    updated = find_callback(load_callbacks(path), entry["id"])
    assert updated["status"] == "discando"
    assert updated["attempts"] == 1


def test_mark_callback_calling_rejects_unknown_id(tmp_path):
    path = tmp_path / "callbacks.json"
    ok, error = mark_callback_calling(path, "nao-existe")
    assert ok is False


def test_mark_callback_result_answered_completes(tmp_path):
    path = tmp_path / "callbacks.json"
    entry = add_callback_request(path, "5511999998888")
    mark_callback_calling(path, entry["id"])

    mark_callback_result(path, entry["id"], "ANSWER")
    updated = find_callback(load_callbacks(path), entry["id"])
    assert updated["status"] == "concluido"


def test_mark_callback_result_retries_then_exhausts(tmp_path):
    """MAX_ATTEMPTS de callback é 2 (menor que campanha) - clientes esperando não devem ser insistidos demais."""
    path = tmp_path / "callbacks.json"
    entry = add_callback_request(path, "5511999998888")

    mark_callback_calling(path, entry["id"])
    mark_callback_result(path, entry["id"], "NOANSWER")
    assert find_callback(load_callbacks(path), entry["id"])["status"] == "pendente"

    mark_callback_calling(path, entry["id"])
    mark_callback_result(path, entry["id"], "NOANSWER")
    assert find_callback(load_callbacks(path), entry["id"])["status"] == "esgotado"


# ---------- extract_dialed_number ----------

def test_extract_dialed_number_from_dialstring():
    event = {"Dialstring": "PJSIP/5511999998888@gateway-tdm"}
    assert extract_dialed_number(event) == "5511999998888"
