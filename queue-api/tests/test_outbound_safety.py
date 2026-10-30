"""Disk-safe multi-process outbound claims and evidence-gated recovery."""
import json
import multiprocessing
import os
import time

import pytest

from outbound_safety import outbound_lock, atomic_write_json
from campaigns import create_campaign, load_campaigns, mark_contact_calling, mark_contact_result
from callbacks import add_callback_request, load_callbacks, mark_callback_calling, mark_callback_result
from reconcile_outbound import quarantine_claim, inspect_claims


def _increment_under_lock(path, ready):
    """Independent process, simulating a second queue-api replica."""
    from outbound_safety import outbound_lock, atomic_write_json
    ready.wait(5)
    with outbound_lock(path):
        records = json.loads(open(path).read())
        time.sleep(0.06)
        records["counter"] += 1
        atomic_write_json(path, records)


def test_two_processes_update_same_shared_snapshot_without_lost_writes(tmp_path):
    path = tmp_path / "outbound.json"
    atomic_write_json(path, {"counter": 0})
    ctx = multiprocessing.get_context("spawn")
    ready = ctx.Event()
    jobs = [ctx.Process(target=_increment_under_lock, args=(str(path), ready))
            for _ in range(2)]
    for job in jobs:
        job.start()
    ready.set()
    for job in jobs:
        job.join(12)
        assert job.exitcode == 0
    assert json.loads(path.read_text()) == {"counter": 2}


def test_atomic_json_replacement_preserves_permissions_and_valid_snapshot(tmp_path):
    path = tmp_path / "campaigns.json"
    atomic_write_json(path, [{"id": "original", "status": "pending"}])
    assert path.stat().st_mode & 0o777 == 0o600
    atomic_write_json(path, [{"id": "second", "status": "discando"}])
    assert json.loads(path.read_text())[0]["id"] == "second"
    assert not list(tmp_path.glob(".campaigns.json.*"))


def test_atomic_json_keeps_previous_file_when_rename_fails(tmp_path, monkeypatch):
    import outbound_safety
    path = tmp_path / "callbacks.json"
    atomic_write_json(path, [{"id": "original"}])
    def fail(*args):
        raise OSError("interrupted before rename")
    monkeypatch.setattr(outbound_safety.os, "replace", fail)
    with pytest.raises(OSError):
        atomic_write_json(path, [{"id": "new"}])
    assert json.loads(path.read_text()) == [{"id": "original"}]
    assert not list(tmp_path.glob(".callbacks.json.*"))


def test_lock_symlink_is_rejected_even_when_target_exists(tmp_path):
    path = tmp_path / "outbound.json"
    target = tmp_path / "elsewhere"
    target.write_text("safe")
    (tmp_path / "outbound.json.lock").symlink_to(target)
    with pytest.raises(OSError):
        with outbound_lock(path):
            pass
    assert target.read_text() == "safe"


def test_quarantine_callback_is_audited_and_never_requeued(tmp_path, monkeypatch):
    path = tmp_path / "callbacks.json"
    callback = add_callback_request(path, "11999998888", "cliente", tenant="t1")
    assert mark_callback_calling(path, callback["id"])[0] is True
    items = load_callbacks(path)
    items[0]["last_attempt_at"] = time.time() - 1800
    atomic_write_json(path, items)
    assert len(inspect_claims(path, "callbacks", "t1")) == 1
    assert inspect_claims(path, "callbacks", "t2") == []
    with pytest.raises(ValueError):
        quarantine_claim(path, "callbacks", "t1", callback["id"],
                         "short", "ops-team")
    result = quarantine_claim(path, "callbacks", "t1", callback["id"],
                              "CDR auditado: nenhuma chamada nova autorizada", "ops-team")
    assert result["status"] == "revisao_manual"
    assert load_callbacks(path)[0]["status"] == "revisao_manual"
    assert inspect_claims(path, "callbacks", "t1") == []
    events = [json.loads(x) for x in (tmp_path / "callbacks.json.audit.jsonl").read_text().splitlines()]
    assert [e["phase"] for e in events] == ["requested", "committed"]
    assert all(e["tenant"] == "t1" for e in events)
    assert "11999998888" not in json.dumps(events)
    assert mark_callback_result(path, callback["id"], "NOANSWER")[0] is False
    assert load_callbacks(path)[0]["status"] == "revisao_manual"


def test_campaign_contact_quarantine_requires_exact_tenant_and_number(tmp_path):
    path = tmp_path / "campaigns.json"
    input_data = {"name": "teste", "agent_extension": "t10-recepcao",
                  "tenant": "t10", "contacts": ["11999998888"]}
    ok, _, campaign = create_campaign(path, input_data)
    assert ok
    number = campaign["contacts"][0]["number"]
    assert mark_contact_calling(path, campaign["id"], number)[0]
    items = load_campaigns(path)
    items[0]["contacts"][0]["last_attempt_at"] = time.time() - 3600
    atomic_write_json(path, items)
    assert inspect_claims(path, "campaigns", "t1") == []
    assert len(inspect_claims(path, "campaigns", "t10")) == 1
    for tenant, number_arg in (("t1", number), ("t10", "00000000"), ("t10", None)):
        with pytest.raises(ValueError):
            quarantine_claim(path, "campaigns", tenant, campaign["id"],
                             "Revisão CDR confirmada nesta instância", "supervisor",
                             number=number_arg)
    result = quarantine_claim(path, "campaigns", "t10", campaign["id"],
                              "Revisão CDR confirmada nesta instância", "supervisor",
                              number=number)
    assert result["status"] == "revisao_manual"
    assert mark_contact_result(path, campaign["id"], number, "NOANSWER")[0] is False
    assert load_campaigns(path)[0]["contacts"][0]["status"] == "revisao_manual"


def test_fresh_claim_cannot_be_quarantined_and_never_auto_redials(tmp_path):
    path = tmp_path / "callbacks.json"
    callback = add_callback_request(path, "11999998888", tenant="t2")
    mark_callback_calling(path, callback["id"])
    assert inspect_claims(path, "callbacks", "t2") == []
    with pytest.raises(ValueError):
        quarantine_claim(path, "callbacks", "t2", callback["id"],
                         "Evidência insuficiente para encaminhar nova chamada", "supervisor")
    assert load_callbacks(path)[0]["status"] == "discando"


def test_audit_log_rejects_non_object_and_oversize_entries(tmp_path):
    from outbound_safety import audit_event
    path = tmp_path / "callbacks.json"
    for bad in ([], None, "text", {"detail": "x" * 70000}):
        with pytest.raises(ValueError):
            audit_event(path, bad)
    audit_path = tmp_path / "callbacks.json.audit.jsonl"
    assert not audit_path.exists() or audit_path.read_text() == ""
    audit_event(path, {"event": "callback_cancel", "tenant": "t1"})
    assert "callback_cancel" in audit_path.read_text(encoding="utf-8")
