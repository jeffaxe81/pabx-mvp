from survey import (
    parse_survey_event, extract_operator_from_channel, SurveyStore,
    average_score, score_distribution, summarize_by_operator,
)

SAMPLE_EVENT = {
    "Event": "UserEvent", "UserEvent": "SatisfactionSurvey",
    "Nota": "5", "Operator": "PJSIP/t1-recepcao-00000001",
    "CallerIDNum": "5511999998888", "CallerIDName": "Cliente Teste",
}


# ---------- extract_operator_from_channel ----------

def test_extract_operator_from_valid_channel():
    assert extract_operator_from_channel("PJSIP/t1-recepcao-00000001") == "t1-recepcao"


def test_extract_operator_returns_none_for_empty_or_malformed():
    assert extract_operator_from_channel("") is None
    assert extract_operator_from_channel(None) is None
    assert extract_operator_from_channel("nao-e-um-canal") is None


# ---------- parse_survey_event ----------

def test_parses_valid_survey_event():
    result = parse_survey_event(SAMPLE_EVENT)
    assert result["score"] == 5
    assert result["operator"] == "t1-recepcao"
    assert result["caller_id_num"] == "5511999998888"
    assert len(result["date"]) == 10


def test_ignores_unrelated_events():
    assert parse_survey_event({"Event": "Hangup"}) is None
    assert parse_survey_event({"Event": "UserEvent", "UserEvent": "QualityStats"}) is None


def test_rejects_score_out_of_range():
    assert parse_survey_event({**SAMPLE_EVENT, "Nota": "0"}) is None
    assert parse_survey_event({**SAMPLE_EVENT, "Nota": "6"}) is None


def test_rejects_non_numeric_score():
    assert parse_survey_event({**SAMPLE_EVENT, "Nota": ""}) is None
    assert parse_survey_event({**SAMPLE_EVENT, "Nota": "abc"}) is None


def test_accepts_score_without_operator():
    """Se DIALEDPEERNAME não veio preenchido (ex: fluxo diferente), a nota ainda é válida."""
    event = {**SAMPLE_EVENT, "Operator": ""}
    result = parse_survey_event(event)
    assert result["score"] == 5
    assert result["operator"] is None


# ---------- SurveyStore ----------

def test_store_append_and_load(tmp_path):
    store = SurveyStore(tmp_path / "survey.jsonl")
    store.append({"score": 5, "operator": "t1-recepcao", "date": "2024-01-01"})
    store.append({"score": 3, "operator": "t1-recepcao-2", "date": "2024-01-01"})
    assert len(store.load_all()) == 2


def test_store_query_filters_by_operator(tmp_path):
    store = SurveyStore(tmp_path / "survey.jsonl")
    store.append({"score": 5, "operator": "t1-recepcao", "date": "2024-01-01"})
    store.append({"score": 3, "operator": "t1-recepcao-2", "date": "2024-01-01"})
    assert len(store.query(operator="t1-recepcao")) == 1


def test_store_load_all_missing_file_returns_empty(tmp_path):
    store = SurveyStore(tmp_path / "nao-existe.jsonl")
    assert store.load_all() == []


def test_store_skips_corrupted_lines(tmp_path):
    path = tmp_path / "survey.jsonl"
    path.write_text('{"score": 5, "operator": "t1-recepcao"}\nlixo corrompido\n')
    store = SurveyStore(path)
    assert len(store.load_all()) == 1


# ---------- average_score / score_distribution / summarize_by_operator ----------

def test_average_score_basic():
    records = [{"score": 5}, {"score": 3}, {"score": 4}]
    assert average_score(records) == 4.0


def test_average_score_none_for_empty_list():
    """None, não 0 - '0 de satisfação' seria enganoso quando não há dado nenhum."""
    assert average_score([]) is None


def test_score_distribution_counts_each_note():
    records = [{"score": 5}, {"score": 5}, {"score": 1}]
    dist = score_distribution(records)
    assert dist["5"] == 2
    assert dist["1"] == 1
    assert dist["3"] == 0


def test_summarize_by_operator_groups_correctly():
    records = [
        {"score": 5, "operator": "t1-recepcao"},
        {"score": 3, "operator": "t1-recepcao"},
        {"score": 4, "operator": "t1-recepcao-2"},
    ]
    summary = summarize_by_operator(records)
    assert summary["t1-recepcao"]["average"] == 4.0
    assert summary["t1-recepcao"]["count"] == 2
    assert summary["t1-recepcao-2"]["average"] == 4.0
    assert summary["t1-recepcao-2"]["count"] == 1


def test_summarize_by_operator_uses_placeholder_for_missing_operator():
    records = [{"score": 5, "operator": None}]
    summary = summarize_by_operator(records)
    assert "desconhecido" in summary
