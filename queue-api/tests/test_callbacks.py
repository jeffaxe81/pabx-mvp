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


# Marco 9 — Entrada AMI insegura nunca deve gerar callback acionável.
import pytest


@pytest.mark.parametrize("bad", [
    None, 42, [], {}, "", "1234", "1234567", "1"*21,
    "12345678;Dial(PJSIP/1)", "12345678" + chr(13) + chr(10) + "Action: Originate",
    " 5511999998888", "5511-9999-8888", "anonymous",
    "+", "++5511999998888", "5511999998888a",
])
def test_callback_event_rejects_untrusted_phone_number(bad):
    event = {"Event": "UserEvent", "UserEvent": "CallbackRequest",
             "CallerIDNum": bad}
    assert parse_callback_request_event(event) is None


@pytest.mark.parametrize("bad", [None, False, [], "UserEvent"])
def test_callback_parser_ignores_non_dict_events(bad):
    assert parse_callback_request_event(bad) is None


def test_callback_accepts_international_plus_and_canonicalizes_digits():
    event = {"Event": "UserEvent", "UserEvent": "CallbackRequest",
             "CallerIDNum": "+5511999998888", "CallerIDName": "Contato"}
    assert parse_callback_request_event(event) == {
        "caller_id_num": "5511999998888", "caller_id_name": "Contato"}


@pytest.mark.parametrize("bad_name", [None, {"x": 1}, "A"*81, "nome" + chr(13) + chr(10) + "Header: x"])
def test_callback_event_strips_unsafe_caller_name(bad_name):
    event = {"Event": "UserEvent", "UserEvent": "CallbackRequest",
             "CallerIDNum": "5511999998888", "CallerIDName": bad_name}
    result = parse_callback_request_event(event)
    assert result["caller_id_num"] == "5511999998888"
    assert result["caller_id_name"] == ""


def test_callback_store_fails_closed_before_writing_invalid_number(tmp_path):
    path = tmp_path / "callbacks.json"
    assert add_callback_request(path, " 5511999998888") is None
    assert not path.exists()
    assert add_callback_request(path, "5511999998888", tenant="t01") is None
    assert not path.exists()
    item = add_callback_request(path, "5511999998888", tenant="t10")
    assert item is not None and item["tenant"] == "t10"
    assert load_callbacks(path)[0]["caller_id_num"] == "5511999998888"


# Registros persistidos não confiáveis: não originar a partir de FIFO corrupto.
@pytest.mark.parametrize("bad", [
    None, 8, "10", False, float("nan"), float("inf"), -1, [],
])
def test_pending_callback_with_bad_timestamp_blocks_entire_fifo(bad):
    good = {"id": "good", "status": "pendente", "requested_at": 200,
            "caller_id_num": "5511999998888", "tenant": "t1"}
    malformed = {**good, "id": "bad", "requested_at": bad}
    assert next_pending_callback([good, malformed]) is None
    assert next_pending_callback([malformed, good]) is None


@pytest.mark.parametrize("malformed", [
    None, "not-an-object", {"status": "pendente", "id": "", "requested_at": 1},
    {"status": "pendente", "id": "bad", "requested_at": 1,
     "caller_id_num": "evil"},
    {"status": "pendente", "id": "bad", "requested_at": 1,
     "caller_id_num": "5511999998888", "tenant": "t01"},
])
def test_malformed_persisted_callback_fails_closed(malformed):
    valid = {"id": "good", "status": "pendente", "requested_at": 100,
             "caller_id_num": "5511999998888", "tenant": "t10"}
    assert next_pending_callback([malformed, valid]) is None


def test_finite_timestamp_preserves_global_fifo_and_tenant_scoping():
    records = [
        {"id": "old-t10", "status": "pendente", "requested_at": 50,
         "caller_id_num": "5511999998888", "tenant": "t10"},
        {"id": "t1", "status": "pendente", "requested_at": 100,
         "caller_id_num": "5511988877777", "tenant": "t1"},
        {"id": "new-t10", "status": "pendente", "requested_at": 200,
         "caller_id_num": "5511988877777", "tenant": "t10"},
    ]
    assert next_pending_callback(records)["id"] == "old-t10"
    owned = [c for c in records if c["tenant"] == "t1"]
    assert next_pending_callback(owned)["id"] == "t1"
    assert next_pending_callback(records[2:])["id"] == "new-t10"


def test_fifo_rejects_non_list_snapshot_without_crashing():
    for malformed in ({}, "pending", None, False):
        assert next_pending_callback(malformed) is None
