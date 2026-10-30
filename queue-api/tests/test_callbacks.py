from callbacks import (
    parse_callback_request_event, add_callback_request, load_callbacks,
    find_callback, next_pending_callback, mark_callback_calling,
    mark_callback_result, extract_dialed_number, cancel_pending_callback,
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


def test_unknown_dial_status_keeps_callback_reserved(tmp_path):
    path = tmp_path / "callbacks.json"
    item = add_callback_request(path, "5511999998888", tenant="t10")
    assert mark_callback_calling(path, item["id"])[0]
    before = path.read_bytes()
    for value in (None, False, 9, [], {}, "", "SUCCESS", "ANSWERED", "TIMEOUT"):
        ok, error = mark_callback_result(path, item["id"], value)
        assert ok is False
        assert error
        assert path.read_bytes() == before
    assert mark_callback_result(path, item["id"], "NOANSWER")[0]


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
    None, "10", False, float("nan"), float("inf"), -1, [],
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



# Marco 9 — identidade de callback única em todo o catálogo persistido.
def test_duplicate_callback_id_across_tenants_never_claims_or_updates(tmp_path):
    from callbacks import save_callbacks
    path = tmp_path / "callbacks.json"
    own = add_callback_request(path, "5511999998888", tenant="t1")
    other = {**own, "tenant": "t10", "caller_id_num": "5511988877777"}
    save_callbacks(path, [own, other])
    before = path.read_bytes()
    with pytest.raises(ValueError, match="duplicados"):
        load_callbacks(path)
    with pytest.raises(ValueError, match="duplicados"):
        mark_callback_calling(path, own["id"])
    with pytest.raises(ValueError, match="duplicados"):
        mark_callback_result(path, own["id"], "ANSWER")
    with pytest.raises(ValueError, match="duplicados"):
        add_callback_request(path, "5511999998888", tenant="t2")
    assert path.read_bytes() == before


def test_duplicate_id_even_when_second_request_finished_blocks_lookup(tmp_path):
    from callbacks import save_callbacks
    path = tmp_path / "callbacks.json"
    first = add_callback_request(path, "5511999998888", tenant="t1")
    second = {**first, "status": "concluido", "tenant": "t2"}
    save_callbacks(path, [first, second])
    with pytest.raises(ValueError, match="duplicados"):
        load_callbacks(path)
    with pytest.raises(ValueError, match="duplicados"):
        mark_callback_calling(path, first["id"])


@pytest.mark.parametrize("invalid", [None, 2, "", False, {}, []])
def test_malformed_callback_catalog_id_fails_closed(invalid):
    other = {"id": "valid", "status": "pendente", "requested_at": 100}
    malformed = {"id": invalid, "status": "concluido"}
    assert find_callback([other, malformed], "valid") is None
    assert next_pending_callback([other, malformed]) is None


def test_generated_callback_id_collision_does_not_overwrite(tmp_path, monkeypatch):
    import callbacks
    path = tmp_path / "callbacks.json"
    existing = add_callback_request(path, "5511999998888", tenant="t1")
    before = path.read_bytes()
    monkeypatch.setattr(callbacks.secrets, "token_hex", lambda _: existing["id"])
    assert add_callback_request(path, "5511999997777", tenant="t2") is None
    assert path.read_bytes() == before


@pytest.mark.parametrize("bad_attempts", [None, -1, 2, 999, "1", False, 0.5])
def test_corrupt_pending_attempt_counter_prevents_originate(tmp_path, bad_attempts):
    from callbacks import save_callbacks
    path = tmp_path / "callbacks.json"
    record = add_callback_request(path, "5511999998888", tenant="t1")
    save_callbacks(path, [{**record, "attempts": bad_attempts}])
    before = path.read_bytes()
    # O loader agora rejeita o snapshot antes de qualquer reserva.
    with pytest.raises(ValueError, match="pendente inconsistente"):
        mark_callback_calling(path, record["id"])
    assert path.read_bytes() == before


@pytest.mark.parametrize("bad_attempts", [None, -1, 0, 3, "1", True, 1.5])
def test_corrupt_dialing_counter_prevents_ami_result_mutation(tmp_path, bad_attempts):
    from callbacks import save_callbacks
    path = tmp_path / "callbacks.json"
    record = add_callback_request(path, "5511999998888", tenant="t1")
    assert mark_callback_calling(path, record["id"])[0]
    record = load_callbacks(path)[0]
    save_callbacks(path, [{**record, "attempts": bad_attempts}])
    before = path.read_bytes()
    assert mark_callback_result(path, record["id"], "ANSWER")[0] is False
    assert path.read_bytes() == before


# Persistência: JSON existente e ambíguo nunca equivale a lista vazia.
@pytest.mark.parametrize("raw", [
    '{"unexpected": "object"}',
    'null',
    '[{"id": "same", "status": "pendente", "requested_at": 1},'
    ' {"id": "same", "status": "pendente", "requested_at": 2}]',
    '[{"id": "valid", "status": "pendente", "status": "discando",'
    ' "requested_at": 1}]',
    '[{"id": "valid", "status": "pendente", "requested_at": NaN}]',
    '[{"id": "valid", "status": "pendente", "requested_at": Infinity}]',
    '[{"id": "valid", "status": "pendente", "requested_at": 1,'
    ' "nested": {"tenant": "t1", "tenant": "t10"}}]',
    '{"id": "valid"} garbage',
])
def test_callback_loader_refuses_corrupt_json_without_rewriting(tmp_path, raw):
    path = tmp_path / "callbacks.json"
    path.write_text(raw, encoding="utf-8")
    original = path.read_bytes()
    with pytest.raises((ValueError, __import__("json").JSONDecodeError)):
        load_callbacks(path)
    assert path.read_bytes() == original
    with pytest.raises((ValueError, __import__("json").JSONDecodeError)):
        add_callback_request(path, "5511999998888", tenant="t1")
    assert path.read_bytes() == original


def test_callback_loader_rejects_symlink(tmp_path):
    data = tmp_path / "real.json"
    data.write_text("[]", encoding="utf-8")
    linked = tmp_path / "callbacks.json"
    linked.symlink_to(data)
    with pytest.raises(ValueError, match="simbolico"):
        load_callbacks(linked)
    assert data.read_text(encoding="utf-8") == "[]"


def test_callback_loader_accepts_empty_or_valid_catalog(tmp_path):
    path = tmp_path / "callbacks.json"
    assert load_callbacks(path) == []
    entry = add_callback_request(path, "5511999998888", tenant="t1")
    assert entry["tenant"] == "t1"
    assert load_callbacks(path)[0]["id"] == entry["id"]


# Marco 9 — um pedido pendente inválido não pode parecer fila vazia.
@pytest.mark.parametrize("field,value", [
    ("caller_id_num", None),
    ("caller_id_num", ""),
    ("caller_id_num", "+5511999998888"),
    ("caller_id_num", "5511999998888;CALL"),
    ("requested_at", None),
    ("requested_at", True),
    ("requested_at", "100"),
    ("requested_at", float("nan")),
    ("requested_at", float("inf")),
    ("requested_at", -1),
    ("attempts", None),
    ("attempts", False),
    ("attempts", "0"),
    ("attempts", -1),
    ("attempts", 2),
    ("tenant", "t01"),
    ("tenant", ["t1"]),
])
def test_pending_callback_corruption_fails_closed_before_dispatch(tmp_path, field, value):
    from callbacks import save_callbacks
    path = tmp_path / "callbacks.json"
    good = add_callback_request(path, "5511999998888", tenant="t1")
    save_callbacks(path, [{**good, field: value}])
    before = path.read_bytes()
    # NaN/Infinity são rejeitados ainda no parse JSON; os demais
    # campos inválidos falham na validação do registro pendente.
    with pytest.raises(ValueError):
        load_callbacks(path)
    with pytest.raises(ValueError):
        mark_callback_calling(path, good["id"])
    assert path.read_bytes() == before


def test_foreign_tenant_corrupt_pending_record_blocks_global_snapshot(tmp_path):
    from callbacks import save_callbacks
    path = tmp_path / "callbacks.json"
    t1 = add_callback_request(path, "5511999998888", tenant="t1")
    t10 = add_callback_request(path, "5511988877777", tenant="t10")
    save_callbacks(path, [t1, {**t10, "requested_at": "bad"}])
    before = path.read_bytes()
    with pytest.raises(ValueError, match="pendente inconsistente"):
        load_callbacks(path)
    assert path.read_bytes() == before


def test_legacy_callback_without_tenant_remains_readable_but_not_authorized(tmp_path):
    path = tmp_path / "callbacks.json"
    legacy = add_callback_request(path, "5511999998888")
    assert load_callbacks(path)[0]["id"] == legacy["id"]
    assert load_callbacks(path)[0].get("tenant") is None


def test_closed_callback_historical_fields_do_not_block_pending_queue(tmp_path):
    from callbacks import save_callbacks
    path = tmp_path / "callbacks.json"
    good = add_callback_request(path, "5511999998888", tenant="t1")
    closed = {**good, "id": "archived", "status": "concluido",
              "caller_id_num": None, "attempts": "legacy"}
    save_callbacks(path, [closed, good])
    assert next_pending_callback(load_callbacks(path))["id"] == good["id"]


# Marco 9 — cancelamento explícito somente de callbacks ainda pendentes.
def test_cancel_pending_callback_persists_status_without_dialing(tmp_path):
    path = tmp_path / "callbacks.json"
    entry = add_callback_request(path, "5511999998888", tenant="t1")
    ok, status = cancel_pending_callback(path, entry["id"], "t1")
    assert (ok, status) == (True, "cancelado")
    stored = load_callbacks(path)[0]
    assert stored["id"] == entry["id"]
    assert stored["status"] == "cancelado"
    assert type(stored["cancelled_at"]) is float
    assert stored["attempts"] == 0
    assert next_pending_callback(load_callbacks(path)) is None


def test_cancel_callback_never_changes_other_tenant_or_legacy(tmp_path):
    path = tmp_path / "callbacks.json"
    own = add_callback_request(path, "5511999998888", tenant="t1")
    other = add_callback_request(path, "5511999997777", tenant="t10")
    legacy = add_callback_request(path, "5511999996666")
    before = path.read_bytes()
    for target in (other, legacy):
        assert cancel_pending_callback(path, target["id"], "t1") == (
            False, "not_found")
    assert path.read_bytes() == before
    assert cancel_pending_callback(path, own["id"], "t1")[0] is True
    records = load_callbacks(path)
    assert next(item for item in records if item["id"] == other["id"])["status"] == "pendente"
    assert next(item for item in records if item["id"] == legacy["id"])["status"] == "pendente"


def test_callback_cancel_refuses_dialing_and_repeat_without_rewriting(tmp_path):
    path = tmp_path / "callbacks.json"
    entry = add_callback_request(path, "5511999998888", tenant="t1")
    assert mark_callback_calling(path, entry["id"])[0] is True
    before = path.read_bytes()
    assert cancel_pending_callback(path, entry["id"], "t1") == (False, "not_pending")
    assert path.read_bytes() == before
    other = add_callback_request(path, "5511999997777", tenant="t1")
    assert cancel_pending_callback(path, other["id"], "t1")[0] is True
    after = path.read_bytes()
    assert cancel_pending_callback(path, other["id"], "t1") == (False, "not_pending")
    assert path.read_bytes() == after


@pytest.mark.parametrize("bad", [
    None, False, "", "AAAAAAAABBBB", "1" * 11, "1" * 13,
    "a" * 12 + "/other", "%2e%2e", {"id": "a" * 12}
])
def test_cancel_invalid_callback_id_never_rewrites(tmp_path, bad):
    path = tmp_path / "callbacks.json"
    add_callback_request(path, "5511999998888", tenant="t1")
    before = path.read_bytes()
    assert cancel_pending_callback(path, bad, "t1") == (False, "not_found")
    assert path.read_bytes() == before


@pytest.mark.parametrize("tenant", [None, "t01", "t1x", "t10\n", False, {}])
def test_cancel_invalid_tenant_never_rewrites(tmp_path, tenant):
    path = tmp_path / "callbacks.json"
    entry = add_callback_request(path, "5511999998888", tenant="t1")
    before = path.read_bytes()
    assert cancel_pending_callback(path, entry["id"], tenant) == (False, "not_found")
    assert path.read_bytes() == before


def test_callback_summary_groups_by_tenant_without_personal_data(tmp_path):
    from callbacks import summarize_callbacks
    path = tmp_path / "callbacks.json"
    t1 = add_callback_request(path, "5511999998888", tenant="t1")
    t10 = add_callback_request(path, "5511999997777", tenant="t10")
    add_callback_request(path, "5511999996666")
    assert cancel_pending_callback(path, t1["id"], "t1")[0]
    records = load_callbacks(path)
    summary = summarize_callbacks(records, "t1")
    assert summary["total"] == 1
    assert summary["by_status"]["cancelado"] == 1
    assert summary["by_status"]["pendente"] == 0
    assert "551199" not in str(summary)
    assert summarize_callbacks(records, "t10")["by_status"]["pendente"] == 1
    assert summarize_callbacks(records, "t2")["total"] == 0
    with pytest.raises(ValueError, match="tenant"):
        summarize_callbacks(records, "t01")
    with pytest.raises(ValueError, match="ambiguo"):
        summarize_callbacks(records + [records[0]], "t1")


# Programa 30 frentes — callbacks: cinco KPIs para supervisão.
def test_30_callback_summary_pending_count_is_tenant_scoped():
    from callbacks import summarize_callbacks
    records = [{"id": "a", "tenant": "t1", "status": "pendente", "requested_at": 50},
               {"id": "b", "tenant": "t10", "status": "pendente", "requested_at": 10}]
    assert summarize_callbacks(records, "t1", now=100)["pending"] == 1
    assert summarize_callbacks(records, "t2", now=100)["pending"] == 0


def test_30_callback_summary_counts_dialing_without_pending():
    from callbacks import summarize_callbacks
    records = [{"id": "a", "tenant": "t1", "status": "discando"}]
    output = summarize_callbacks(records, "t1", now=100)
    assert output["dialing"] == 1
    assert output["pending"] == 0


def test_30_callback_summary_counts_completed_separately():
    from callbacks import summarize_callbacks
    records = [{"id": "a", "tenant": "t1", "status": "concluido"},
               {"id": "b", "tenant": "t10", "status": "concluido"}]
    output = summarize_callbacks(records, "t1", now=100)
    assert output["completed"] == 1
    assert output["total"] == 1


def test_30_callback_summary_cancellations_do_not_count_as_completions():
    from callbacks import summarize_callbacks
    records = [{"id": "a", "tenant": "t1", "status": "cancelado"}]
    output = summarize_callbacks(records, "t1", now=100)
    assert output["cancelled"] == 1
    assert output["completed"] == 0


def test_30_callback_summary_oldest_wait_excludes_other_tenant_and_future():
    from callbacks import summarize_callbacks
    records = [{"id": "a", "tenant": "t1", "status": "pendente", "requested_at": 70},
               {"id": "b", "tenant": "t1", "status": "pendente", "requested_at": 80},
               {"id": "c", "tenant": "t10", "status": "pendente", "requested_at": 1}]
    assert summarize_callbacks(records, "t1", now=100)["oldest_pending_seconds"] == 30
    assert summarize_callbacks(records, "t1", now=10)["oldest_pending_seconds"] == 0
    assert summarize_callbacks([], "t1", now=100)["oldest_pending_seconds"] is None
    with pytest.raises(ValueError, match="relogio"):
        summarize_callbacks(records, "t1", now=float("nan"))
    with pytest.raises(ValueError, match="data"):
        summarize_callbacks([{**records[0], "requested_at": "bad"}], "t1", now=100)
