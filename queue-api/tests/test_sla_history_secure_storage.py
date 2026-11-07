"""SLA privado: teste de persistência real, isolamento de arquivo e dados."""
import json
import os
from pathlib import Path
import stat

import pytest

import queue_sla
from queue_sla import SLAHistoryStore


GOOD = {"date": "2026-11-07", "queue": "fila-t1",
        "offered": 10, "within_sla": 8, "sla_percent": 999.0}


def test_private_append_reads_only_recomputed_sla(tmp_path):
    path = tmp_path / "private" / "history.jsonl"
    store = SLAHistoryStore(path)
    store.append(GOOD)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert store.load_all() == [{
        "date": "2026-11-07", "queue": "fila-t1",
        "offered": 10, "within_sla": 8, "sla_percent": 80.0
    }]
    store.append({"date": "2026-11-07", "queue": "fila-t10",
                  "offered": 4, "within_sla": 1, "sla_percent": -1.0})
    assert len(store.load_all()) == 2
    assert [entry["queue"] for entry in store.load_all()] == [
        "fila-t1", "fila-t10"
    ]


@pytest.mark.parametrize("bad", [
    None, [], "texto", {},
    {**GOOD, "date": "2026-02-30"},
    {**GOOD, "date": "2026-11-07\n"},
    {**GOOD, "queue": "fila-t1\ninjected"},
    {**GOOD, "offered": True},
    {**GOOD, "offered": -1},
    {**GOOD, "offered": 10_000_001},
    {**GOOD, "within_sla": 11},
    {**GOOD, "within_sla": -1},
    {**GOOD, "within_sla": 2.0},
])
def test_append_invalid_sla_refuses_write(tmp_path, bad):
    path = tmp_path / "secure.jsonl"
    with pytest.raises(ValueError, match="inválido"):
        SLAHistoryStore(path).append(bad)
    assert not path.exists()


def test_symlink_final_is_never_followed(tmp_path):
    secret = tmp_path / "protected.jsonl"
    secret.write_text("DO_NOT_TOUCH", encoding="utf-8")
    alias = tmp_path / "alias.jsonl"
    alias.symlink_to(secret)
    store = SLAHistoryStore(alias)
    with pytest.raises(ValueError):
        store.append(GOOD)
    with pytest.raises(ValueError):
        store.load_all()
    assert secret.read_text(encoding="utf-8") == "DO_NOT_TOUCH"


def test_symlink_ancestor_is_never_followed(tmp_path):
    parent = tmp_path / "target"
    parent.mkdir()
    alias = tmp_path / "symlink-dir"
    alias.symlink_to(parent, target_is_directory=True)
    store = SLAHistoryStore(alias / "history.jsonl")
    with pytest.raises(ValueError):
        store.append(GOOD)
    with pytest.raises(ValueError):
        store.load_all()
    assert list(parent.iterdir()) == []


def test_hardlink_does_not_rewrite_shared_inode(tmp_path):
    original = tmp_path / "original.jsonl"
    original.write_text("PRESERVE", encoding="utf-8")
    alias = tmp_path / "hardlink.jsonl"
    os.link(original, alias)
    store = SLAHistoryStore(alias)
    with pytest.raises(ValueError):
        store.append(GOOD)
    with pytest.raises(ValueError):
        store.load_all()
    assert original.read_text(encoding="utf-8") == "PRESERVE"


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="plataforma sem FIFO")
def test_fifo_is_rejected_without_blocking(tmp_path):
    path = tmp_path / "pipe.jsonl"
    os.mkfifo(path)
    store = SLAHistoryStore(path)
    with pytest.raises(ValueError):
        store.load_all()
    with pytest.raises(ValueError):
        store.append(GOOD)


def test_legacy_file_is_tightened_on_append(tmp_path):
    path = tmp_path / "historico.jsonl"
    path.write_text(json.dumps(GOOD) + "\n", encoding="utf-8")
    path.chmod(0o644)
    store = SLAHistoryStore(path)
    store.append(GOOD)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert len(store.load_all()) == 2


def test_read_rejects_large_file_without_loading_all(tmp_path, monkeypatch):
    path = tmp_path / "history.jsonl"
    path.write_text(json.dumps(GOOD) * 20, encoding="utf-8")
    monkeypatch.setattr(queue_sla, "MAX_HISTORY_BYTES", 256)
    store = SLAHistoryStore(path)
    with pytest.raises(ValueError, match="limite"):
        store.load_all()
    with pytest.raises(ValueError, match="limite"):
        store.append(GOOD)


def test_malformed_json_is_skipped_and_duplicate_keys_fail_closed(tmp_path):
    path = tmp_path / "history.jsonl"
    bad_duplicate = (
        '{"date":"2026-11-07","queue":"fila-t1","offered":1,'
        '"offered":100000,"within_sla":1}'
    )
    path.write_text("\n".join((
        "garbage", bad_duplicate,
        '{"date":"2026-11-07","queue":"fila-t1","offered":NaN,"within_sla":1}',
        json.dumps(GOOD), ""
    )), encoding="utf-8")
    records = SLAHistoryStore(path).load_all()
    assert len(records) == 1
    assert records[0]["sla_percent"] == 80.0


def test_missing_history_returns_empty_without_creating_directory(tmp_path):
    path = tmp_path / "nonexistent" / "history.jsonl"
    assert SLAHistoryStore(path).load_all() == []
    assert not path.parent.exists()


def test_reject_parent_traversal_and_extraneous_files(tmp_path):
    store = SLAHistoryStore(tmp_path / ".." / "other.jsonl")
    with pytest.raises(ValueError):
        store.append(GOOD)
    with pytest.raises(ValueError):
        store.load_all()


def test_small_size_limit_refuses_new_history(tmp_path, monkeypatch):
    monkeypatch.setattr(queue_sla, "MAX_HISTORY_BYTES", 10)
    with pytest.raises(ValueError, match="limite"):
        SLAHistoryStore(tmp_path / "sla.jsonl").append(GOOD)
