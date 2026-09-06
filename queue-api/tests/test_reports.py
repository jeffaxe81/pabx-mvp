from reports import (
    extract_operator, extract_tenant, parse_cdr_for_report,
    CallLogStore, aggregate, group_by,
)


# ---------- extract_operator / extract_tenant ----------

def test_extract_operator_from_channel_name():
    assert extract_operator("PJSIP/t1-recepcao-00000003") == "t1-recepcao"


def test_extract_operator_returns_none_for_malformed_channel():
    assert extract_operator("nao-e-um-canal-sip") is None
    assert extract_operator("") is None
    assert extract_operator(None) is None


def test_extract_tenant_from_operator_prefix():
    assert extract_tenant("t1-recepcao", "algum-contexto") == "t1"


def test_extract_tenant_falls_back_to_context():
    assert extract_tenant(None, "t2-internal") == "t2"


def test_extract_tenant_returns_none_when_no_pattern_matches():
    assert extract_tenant("gateway-tdm", "from-tdm-gateway") is None


# ---------- parse_cdr_for_report ----------

def test_parse_answered_call_with_operator():
    event = {
        "Event": "Cdr", "Disposition": "ANSWERED", "BillableSeconds": "125",
        "DestinationChannel": "PJSIP/t1-recepcao-00000001",
        "DestinationContext": "t1-internal",
        "EndTime": "2024-03-10 14:22:01", "CallerIDNum": "5511999998888",
    }
    record = parse_cdr_for_report(event)
    assert record["date"] == "2024-03-10"
    assert record["operator"] == "t1-recepcao"
    assert record["tenant"] == "t1"
    assert record["billable_seconds"] == 125
    assert record["disposition"] == "ANSWERED"


def test_parse_missed_call_has_zero_billable_seconds_even_if_present():
    event = {"Event": "Cdr", "Disposition": "NO ANSWER", "BillableSeconds": "0"}
    record = parse_cdr_for_report(event)
    assert record["billable_seconds"] == 0
    assert record["operator"] is None


def test_parse_ignores_non_cdr_events():
    assert parse_cdr_for_report({"Event": "Hangup"}) is None


def test_parse_ignores_cdr_without_disposition():
    assert parse_cdr_for_report({"Event": "Cdr"}) is None


def test_parse_handles_missing_end_time_gracefully():
    event = {"Event": "Cdr", "Disposition": "ANSWERED", "BillableSeconds": "10"}
    record = parse_cdr_for_report(event)
    assert len(record["date"]) == 10  # formato YYYY-MM-DD, mesmo sem EndTime


def test_parse_handles_invalid_billable_seconds():
    event = {"Event": "Cdr", "Disposition": "ANSWERED", "BillableSeconds": "abc"}
    assert parse_cdr_for_report(event)["billable_seconds"] == 0


# ---------- CallLogStore ----------

def test_store_append_and_load(tmp_path):
    store = CallLogStore(tmp_path / "call_log.jsonl")
    store.append({"date": "2024-01-01", "disposition": "ANSWERED", "billable_seconds": 60})
    store.append({"date": "2024-01-02", "disposition": "NO ANSWER", "billable_seconds": 0})

    records = store.load_all()
    assert len(records) == 2


def test_store_query_filters_by_date_range(tmp_path):
    store = CallLogStore(tmp_path / "call_log.jsonl")
    for date in ("2024-01-01", "2024-01-05", "2024-01-10"):
        store.append({"date": date, "disposition": "ANSWERED", "billable_seconds": 10})

    result = store.query(start="2024-01-02", end="2024-01-09")
    assert [r["date"] for r in result] == ["2024-01-05"]


def test_store_query_filters_by_operator_and_tenant(tmp_path):
    store = CallLogStore(tmp_path / "call_log.jsonl")
    store.append({"date": "2024-01-01", "disposition": "ANSWERED", "billable_seconds": 10, "operator": "t1-recepcao", "tenant": "t1"})
    store.append({"date": "2024-01-01", "disposition": "ANSWERED", "billable_seconds": 10, "operator": "t1-recepcao-2", "tenant": "t1"})

    assert len(store.query(operator="t1-recepcao")) == 1
    assert len(store.query(tenant="t1")) == 2


def test_store_load_all_returns_empty_list_when_file_missing(tmp_path):
    store = CallLogStore(tmp_path / "nao-existe.jsonl")
    assert store.load_all() == []


def test_store_skips_corrupted_lines(tmp_path):
    path = tmp_path / "call_log.jsonl"
    path.write_text('{"date": "2024-01-01", "disposition": "ANSWERED", "billable_seconds": 10}\nlinha corrompida\n')
    store = CallLogStore(path)
    assert len(store.load_all()) == 1


# ---------- aggregate / group_by ----------

def test_aggregate_basic_counts():
    records = [
        {"disposition": "ANSWERED", "billable_seconds": 100},
        {"disposition": "ANSWERED", "billable_seconds": 200},
        {"disposition": "NO ANSWER", "billable_seconds": 0},
    ]
    result = aggregate(records)
    assert result["total_calls"] == 3
    assert result["answered_calls"] == 2
    assert result["missed_calls"] == 1
    assert result["average_talk_seconds"] == 150
    assert result["missed_rate_percent"] == round(1 / 3 * 100, 1)


def test_aggregate_empty_list():
    result = aggregate([])
    assert result["total_calls"] == 0
    assert result["average_talk_seconds"] == 0
    assert result["missed_rate_percent"] == 0


def test_group_by_operator():
    records = [
        {"disposition": "ANSWERED", "billable_seconds": 100, "operator": "t1-recepcao"},
        {"disposition": "ANSWERED", "billable_seconds": 50, "operator": "t1-recepcao-2"},
        {"disposition": "NO ANSWER", "billable_seconds": 0, "operator": "t1-recepcao"},
    ]
    grouped = group_by(records, "operator")
    assert grouped["t1-recepcao"]["total_calls"] == 2
    assert grouped["t1-recepcao-2"]["total_calls"] == 1


def test_group_by_uses_placeholder_for_missing_key():
    records = [{"disposition": "ANSWERED", "billable_seconds": 10, "operator": None}]
    grouped = group_by(records, "operator")
    assert "desconhecido" in grouped
