"""20 controles de callback: UserEvent idempotente, tentativas AMI e tenant."""
import json

import pytest

from callbacks import (
    _MAX_CATALOG_BYTES, _MAX_CALLBACKS, add_callback_request, load_callbacks,
    mark_callback_calling, parse_callback_request_event, save_callbacks,
    validate_callback_catalog,
)

PHONE = "5511999998888"
OTHER = "5511988877777"


def event(uniqueid, phone=PHONE):
    return {"Event": "UserEvent", "UserEvent": "CallbackRequest",
            "CallerIDNum": phone, "Tenant": "t1", "Uniqueid": uniqueid}


def make(tmp_path, tenant="t1", number=PHONE):
    path = tmp_path / "callbacks.json"
    record = add_callback_request(path, number, tenant=tenant)
    assert record is not None
    return path, record


def mutate(path, key, value):
    rows = load_callbacks(path)
    rows[0][key] = value
    save_callbacks(path, rows)
    return path


def test_01_persists_uniqueid_on_parsed_user_event(tmp_path):
    path = tmp_path / "cb.json"
    contact = parse_callback_request_event(event("1700000001.42"))
    assert contact["source_uniqueid"] == "1700000001.42"
    saved = add_callback_request(path, contact["caller_id_num"], tenant="t1",
                                 source_uniqueid=contact["source_uniqueid"])
    assert saved["source_uniqueid"] == "1700000001.42"


@pytest.mark.parametrize("bad", ["", "x" * 97, "a\nInjected", "bad id", [],
                                       {}, False, 10])
def test_02_rejects_invalid_source_uniqueid(bad):
    assert parse_callback_request_event(event(bad)) is None


def test_03_same_user_event_replay_is_idempotent(tmp_path):
    path = tmp_path / "cb.json"
    a = add_callback_request(path, PHONE, tenant="t1", source_uniqueid="123.45")
    raw = path.read_bytes()
    b = add_callback_request(path, PHONE, tenant="t1", source_uniqueid="123.45")
    assert b["id"] == a["id"] and path.read_bytes() == raw
    assert len(load_callbacks(path)) == 1


def test_04_conflicting_replayed_uniqueid_never_requeues(tmp_path):
    path = tmp_path / "cb.json"
    assert add_callback_request(path, PHONE, tenant="t1", source_uniqueid="123.45")
    raw = path.read_bytes()
    assert add_callback_request(path, OTHER, tenant="t1", source_uniqueid="123.45") is None
    assert path.read_bytes() == raw


def test_05_source_uniqueid_isolated_by_exact_tenant(tmp_path):
    path = tmp_path / "cb.json"
    a = add_callback_request(path, PHONE, tenant="t1", source_uniqueid="same.1")
    b = add_callback_request(path, PHONE, tenant="t10", source_uniqueid="same.1")
    assert a["id"] != b["id"]
    assert len(load_callbacks(path)) == 2


def test_06_refuses_directory_catalog(tmp_path):
    with pytest.raises(ValueError, match="regular"):
        load_callbacks(tmp_path)


def test_07_refuses_oversize_catalog(tmp_path):
    path = tmp_path / "cb.json"
    path.write_bytes(b" " * (_MAX_CATALOG_BYTES + 1))
    with pytest.raises(ValueError, match="excessivo"):
        load_callbacks(path)


def test_08_rejects_oversized_inventory_without_mutating_disk(tmp_path, monkeypatch):
    import callbacks
    path, _ = make(tmp_path)
    monkeypatch.setattr(callbacks, "_MAX_CALLBACKS", 1)
    original = path.read_bytes()
    assert add_callback_request(path, OTHER, tenant="t1") is None
    assert path.read_bytes() == original


@pytest.mark.parametrize("bad", [[], {}, None, True])
def test_09_rejects_invalid_active_status(tmp_path, bad):
    path, _ = make(tmp_path)
    mutate(path, "status", bad)
    with pytest.raises(ValueError):
        load_callbacks(path)


def test_10_active_id_requires_generated_format(tmp_path):
    path, _ = make(tmp_path)
    mutate(path, "id", "not-hex")
    with pytest.raises(ValueError):
        load_callbacks(path)


@pytest.mark.parametrize("bad", ["+5511999998888", "123", "1" * 21])
def test_11_active_phone_requires_canonical_format(tmp_path, bad):
    path, _ = make(tmp_path)
    mutate(path, "caller_id_num", bad)
    with pytest.raises(ValueError):
        load_callbacks(path)


@pytest.mark.parametrize("bad", ["A\nInjected", "x" * 81, [], {}])
def test_12_active_caller_name_must_be_safe(tmp_path, bad):
    path, _ = make(tmp_path)
    mutate(path, "caller_id_name", bad)
    with pytest.raises(ValueError):
        load_callbacks(path)


@pytest.mark.parametrize("bad", ["t01", "t1x", ["t1"], False])
def test_13_active_tenant_must_be_valid(tmp_path, bad):
    path, _ = make(tmp_path)
    mutate(path, "tenant", bad)
    with pytest.raises(ValueError):
        load_callbacks(path)


@pytest.mark.parametrize("bad", [-1, "100", True, None])
def test_14_active_request_time_must_be_numeric(tmp_path, bad):
    path, _ = make(tmp_path)
    mutate(path, "requested_at", bad)
    with pytest.raises(ValueError):
        load_callbacks(path)


def test_15_pending_request_cannot_have_exhausted_attempts(tmp_path):
    path, _ = make(tmp_path)
    mutate(path, "attempts", 2)
    with pytest.raises(ValueError, match="esgotado"):
        load_callbacks(path)


def test_16_dialing_requires_positive_attempt_counter(tmp_path):
    path, record = make(tmp_path)
    assert mark_callback_calling(path, record["id"])[0]
    mutate(path, "attempts", 0)
    with pytest.raises(ValueError, match="correlacao"):
        load_callbacks(path)


def test_17_dialing_requires_hex32_attempt_id(tmp_path):
    path, record = make(tmp_path)
    assert mark_callback_calling(path, record["id"])[0]
    mutate(path, "attempt_id", "injected")
    with pytest.raises(ValueError, match="correlacao"):
        load_callbacks(path)


def test_18_dialing_requires_exact_channel_identifier(tmp_path):
    path, record = make(tmp_path)
    assert mark_callback_calling(path, record["id"])[0]
    mutate(path, "channel_id", "axe-foreign")
    with pytest.raises(ValueError, match="correlacao"):
        load_callbacks(path)


@pytest.mark.parametrize("bad", [-1, True, None, "2026", float("inf")])
def test_19_dialing_timestamp_must_be_finite(tmp_path, bad):
    path, record = make(tmp_path)
    assert mark_callback_calling(path, record["id"])[0]
    mutate(path, "last_attempt_at", bad)
    with pytest.raises(ValueError):
        load_callbacks(path)


def test_20_dialing_attempt_must_be_unique_even_across_tenants(tmp_path):
    path, t1 = make(tmp_path)
    t10 = add_callback_request(path, OTHER, tenant="t10")
    assert mark_callback_calling(path, t1["id"])[0]
    assert mark_callback_calling(path, t10["id"])[0]
    rows = load_callbacks(path)
    rows[1]["attempt_id"] = rows[0]["attempt_id"]
    rows[1]["channel_id"] = rows[0]["channel_id"]
    save_callbacks(path, rows)
    with pytest.raises(ValueError, match="duplicado"):
        load_callbacks(path)


def test_invalid_ami_response_metadata_does_not_approve_redial(tmp_path):
    path, record = make(tmp_path)
    assert mark_callback_calling(path, record["id"])[0]
    mutate(path, "originate_response", ["Success"])
    with pytest.raises(ValueError, match="AMI"):
        load_callbacks(path)


def test_invalid_response_timestamp_is_rejected(tmp_path):
    path, record = make(tmp_path)
    assert mark_callback_calling(path, record["id"])[0]
    mutate(path, "originate_response_at", -9)
    with pytest.raises(ValueError, match="timestamp"):
        load_callbacks(path)


def test_historical_closed_callback_stays_readable(tmp_path):
    path, record = make(tmp_path)
    historical = {**record, "status": "concluido", "id": "legacy",
                  "caller_id_num": None, "attempts": "legacy"}
    save_callbacks(path, [historical, record])
    assert validate_callback_catalog(load_callbacks(path))
