from campaigns import (
    sanitize_phone_number, validate_campaign_input, create_campaign,
    load_campaigns, find_campaign, next_pending_contact,
    mark_contact_calling, mark_contact_result, campaign_summary,
    extract_dialed_number,
)

VALID_INPUT = {
    "name": "Campanha de cobrança",
    "agent_extension": "t1-recepcao",
    "contacts": ["(11) 99999-8888", "11988887777", "123"],  # o "123" é inválido de propósito
}


# ---------- sanitize_phone_number ----------

def test_sanitize_removes_formatting():
    assert sanitize_phone_number("(11) 99999-8888") == "11999998888"


def test_sanitize_rejects_short_number():
    assert sanitize_phone_number("123") is None


# ---------- validate_campaign_input ----------

def test_validate_accepts_correct_input_and_filters_invalid_numbers():
    ok, error, campaign = validate_campaign_input(VALID_INPUT)
    assert ok is True
    assert campaign["name"] == "Campanha de cobrança"
    assert len(campaign["contacts"]) == 2  # o "123" foi descartado
    assert all(c["status"] == "pendente" for c in campaign["contacts"])


def test_validate_rejects_missing_name():
    ok, error, _ = validate_campaign_input({**VALID_INPUT, "name": ""})
    assert ok is False
    assert "nome" in error


def test_validate_rejects_missing_agent_extension():
    ok, error, _ = validate_campaign_input({**VALID_INPUT, "agent_extension": ""})
    assert ok is False
    assert "ramal" in error


def test_validate_rejects_empty_contact_list():
    ok, error, _ = validate_campaign_input({**VALID_INPUT, "contacts": []})
    assert ok is False
    assert "vazia" in error


def test_validate_rejects_all_invalid_numbers():
    ok, error, _ = validate_campaign_input({**VALID_INPUT, "contacts": ["1", "2", "abc"]})
    assert ok is False
    assert "nenhum número válido" in error


# ---------- create_campaign / persistência ----------

def test_create_campaign_persists_to_disk(tmp_path):
    path = tmp_path / "campaigns.json"
    ok, error, campaign = create_campaign(path, VALID_INPUT)
    assert ok is True
    assert find_campaign(load_campaigns(path), campaign["id"]) is not None


def test_create_campaign_rejects_invalid_data(tmp_path):
    path = tmp_path / "campaigns.json"
    ok, error, campaign = create_campaign(path, {**VALID_INPUT, "name": ""})
    assert ok is False
    assert load_campaigns(path) == []


# ---------- next_pending_contact ----------

def test_next_pending_contact_returns_first_pending():
    campaign = {"contacts": [
        {"number": "1", "status": "atendida"},
        {"number": "2", "status": "pendente"},
        {"number": "3", "status": "pendente"},
    ]}
    assert next_pending_contact(campaign)["number"] == "2"


def test_next_pending_contact_returns_none_when_all_done():
    campaign = {"contacts": [{"number": "1", "status": "atendida"}]}
    assert next_pending_contact(campaign) is None


# ---------- mark_contact_calling / mark_contact_result ----------

def test_mark_contact_calling_increments_attempts(tmp_path):
    path = tmp_path / "campaigns.json"
    _, _, campaign = create_campaign(path, VALID_INPUT)
    number = campaign["contacts"][0]["number"]

    ok, error = mark_contact_calling(path, campaign["id"], number)
    assert ok is True

    updated = find_campaign(load_campaigns(path), campaign["id"])
    contact = next(c for c in updated["contacts"] if c["number"] == number)
    assert contact["status"] == "discando"
    assert contact["attempts"] == 1
    assert contact["last_attempt_at"] is not None


def test_mark_contact_calling_rejects_unknown_campaign(tmp_path):
    path = tmp_path / "campaigns.json"
    ok, error = mark_contact_calling(path, "nao-existe", "11999998888")
    assert ok is False


def test_mark_contact_result_answered_sets_final_status(tmp_path):
    path = tmp_path / "campaigns.json"
    _, _, campaign = create_campaign(path, VALID_INPUT)
    number = campaign["contacts"][0]["number"]
    mark_contact_calling(path, campaign["id"], number)

    mark_contact_result(path, campaign["id"], number, "ANSWER")

    updated = find_campaign(load_campaigns(path), campaign["id"])
    contact = next(c for c in updated["contacts"] if c["number"] == number)
    assert contact["status"] == "atendida"


def test_mark_contact_result_no_answer_retries_until_max_attempts(tmp_path):
    path = tmp_path / "campaigns.json"
    _, _, campaign = create_campaign(path, VALID_INPUT)
    number = campaign["contacts"][0]["number"]

    # 1a e 2a tentativa sem resposta - deve voltar pra "pendente" (retry)
    for _ in range(2):
        mark_contact_calling(path, campaign["id"], number)
        mark_contact_result(path, campaign["id"], number, "NOANSWER")
        updated = find_campaign(load_campaigns(path), campaign["id"])
        contact = next(c for c in updated["contacts"] if c["number"] == number)
        assert contact["status"] == "pendente"

    # 3a tentativa (MAX_ATTEMPTS) sem resposta - agora esgota
    mark_contact_calling(path, campaign["id"], number)
    mark_contact_result(path, campaign["id"], number, "NOANSWER")
    updated = find_campaign(load_campaigns(path), campaign["id"])
    contact = next(c for c in updated["contacts"] if c["number"] == number)
    assert contact["status"] == "esgotado"


def test_mark_contact_result_unknown_disposition_defaults_to_falha(tmp_path):
    path = tmp_path / "campaigns.json"
    _, _, campaign = create_campaign(path, VALID_INPUT)
    number = campaign["contacts"][0]["number"]
    mark_contact_calling(path, campaign["id"], number)

    mark_contact_result(path, campaign["id"], number, "TIPO-DESCONHECIDO")
    updated = find_campaign(load_campaigns(path), campaign["id"])
    contact = next(c for c in updated["contacts"] if c["number"] == number)
    assert contact["status"] == "pendente"  # falha com tentativas < MAX ainda tenta de novo


# ---------- campaign_summary ----------

def test_campaign_summary_counts_by_status():
    campaign = {"contacts": [
        {"status": "pendente"}, {"status": "pendente"}, {"status": "atendida"},
    ]}
    summary = campaign_summary(campaign)
    assert summary["pendente"] == 2
    assert summary["atendida"] == 1
    assert summary["total"] == 3


# ---------- extract_dialed_number ----------

def test_extract_dialed_number_from_dialstring():
    event = {"Event": "DialEnd", "Dialstring": "PJSIP/5511999998888@gateway-tdm"}
    assert extract_dialed_number(event) == "5511999998888"


def test_extract_dialed_number_falls_back_to_dest_exten():
    event = {"Event": "DialEnd", "DestExten": "5511988887777"}
    assert extract_dialed_number(event) == "5511988887777"


def test_extract_dialed_number_returns_none_when_absent():
    assert extract_dialed_number({"Event": "DialEnd"}) is None
