import os
import time

from recordings import list_recordings, safe_recording_path, parse_recording_filename, delete_expired_recordings


def _touch(path, mtime_offset=0):
    path.write_text("dados falsos de audio")
    if mtime_offset:
        t = time.time() + mtime_offset
        os.utime(path, (t, t))


def test_empty_directory_returns_empty_list(tmp_path):
    assert list_recordings(tmp_path) == []


def test_nonexistent_directory_returns_empty_list(tmp_path):
    assert list_recordings(tmp_path / "nao-existe") == []


def test_lists_only_audio_files(tmp_path):
    _touch(tmp_path / "20240101-100000-5511999999999-1000.wav")
    _touch(tmp_path / "notas.txt")
    _touch(tmp_path / "20240101-110000-5511888888888-pickup.wav")

    result = list_recordings(tmp_path)
    filenames = {r["filename"] for r in result}
    assert filenames == {
        "20240101-100000-5511999999999-1000.wav",
        "20240101-110000-5511888888888-pickup.wav",
    }


def test_ordered_newest_first(tmp_path):
    _touch(tmp_path / "antiga.wav", mtime_offset=-100)
    _touch(tmp_path / "nova.wav", mtime_offset=0)

    result = list_recordings(tmp_path)
    assert [r["filename"] for r in result] == ["nova.wav", "antiga.wav"]


def test_respects_limit(tmp_path):
    for i in range(5):
        _touch(tmp_path / f"grav-{i}.wav")

    result = list_recordings(tmp_path, limit=2)
    assert len(result) == 2


def test_includes_size_and_modified_at(tmp_path):
    f = tmp_path / "teste.wav"
    _touch(f)

    result = list_recordings(tmp_path)
    assert result[0]["size_bytes"] > 0
    assert "T" in result[0]["modified_at"]  # formato ISO


def test_safe_recording_path_accepts_valid_file(tmp_path):
    (tmp_path / "grav.wav").write_text("x")
    resolved = safe_recording_path(tmp_path, "grav.wav")
    assert resolved is not None
    assert resolved.name == "grav.wav"


def test_safe_recording_path_blocks_path_traversal(tmp_path):
    secret_dir = tmp_path.parent / "secreto"
    secret_dir.mkdir(exist_ok=True)
    (secret_dir / "segredo.wav").write_text("x")

    resolved = safe_recording_path(tmp_path, "../secreto/segredo.wav")
    assert resolved is None


def test_safe_recording_path_rejects_nonexistent_file(tmp_path):
    assert safe_recording_path(tmp_path, "nao-existe.wav") is None


def test_safe_recording_path_rejects_disallowed_extension(tmp_path):
    (tmp_path / "script.sh").write_text("x")
    assert safe_recording_path(tmp_path, "script.sh") is None


# ---------- parse_recording_filename ----------

def test_parse_filename_extracts_caller_and_destination():
    parsed = parse_recording_filename("20240101-100000-5511999999999-1000.wav")
    assert parsed["timestamp"] == "20240101-100000"
    assert parsed["caller_number"] == "5511999999999"
    assert parsed["destination"] == "1000"


def test_parse_filename_handles_empty_caller_id():
    """Chamada interna sem CALLERID(num) gera nome tipo '...--1000.wav'."""
    parsed = parse_recording_filename("20240101-100000--1000.wav")
    assert parsed["caller_number"] is None
    assert parsed["destination"] == "1000"


def test_parse_filename_returns_none_for_unrecognized_pattern():
    """
    Gravações que vêm do monitor-type da fila usam outro padrão de
    nome (do próprio Asterisk) - não devem quebrar, só não parseiam.
    """
    assert parse_recording_filename("fila-t1-1699999999.12345.wav") is None
    assert parse_recording_filename("qualquer-coisa.wav") is None


# ---------- list_recordings com filtros ----------

def test_filter_by_caller_number(tmp_path):
    _touch(tmp_path / "20240101-100000-5511999999999-1000.wav")
    _touch(tmp_path / "20240101-110000-5511888888888-1000.wav")

    result = list_recordings(tmp_path, caller_number="5511999999999")
    assert len(result) == 1
    assert result[0]["caller_number"] == "5511999999999"


def test_filter_by_destination(tmp_path):
    _touch(tmp_path / "20240101-100000-5511999999999-1000.wav")
    _touch(tmp_path / "20240101-110000-5511999999999-1010.wav")

    result = list_recordings(tmp_path, destination="1010")
    assert len(result) == 1
    assert result[0]["destination"] == "1010"


def test_filter_by_date_range(tmp_path):
    _touch(tmp_path / "20240101-100000-123-1000.wav")
    _touch(tmp_path / "20240115-100000-123-1000.wav")
    _touch(tmp_path / "20240201-100000-123-1000.wav")

    result = list_recordings(tmp_path, start_date="20240110", end_date="20240120")
    assert len(result) == 1
    assert result[0]["filename"] == "20240115-100000-123-1000.wav"


def test_unparseable_filenames_excluded_when_any_filter_is_active(tmp_path):
    """
    Se a pessoa está filtrando por atendente/número, uma gravação sem
    esses dados no nome não pode aparecer misturada no resultado -
    ela não bate no filtro, não é "sem filtro nenhum".
    """
    _touch(tmp_path / "20240101-100000-123-1000.wav")
    _touch(tmp_path / "fila-t1-formato-diferente.wav")

    result = list_recordings(tmp_path, destination="1000")
    assert len(result) == 1


def test_no_filters_includes_unparseable_filenames_too(tmp_path):
    _touch(tmp_path / "20240101-100000-123-1000.wav")
    _touch(tmp_path / "fila-t1-formato-diferente.wav")

    result = list_recordings(tmp_path)
    assert len(result) == 2


# ---------- delete_expired_recordings ----------

def test_retention_disabled_by_default_value_deletes_nothing(tmp_path):
    _touch(tmp_path / "antiga.wav", mtime_offset=-999999)
    deleted = delete_expired_recordings(tmp_path, retention_days=0)
    assert deleted == []
    assert (tmp_path / "antiga.wav").exists()


def test_retention_negative_days_also_disables(tmp_path):
    _touch(tmp_path / "antiga.wav", mtime_offset=-999999)
    assert delete_expired_recordings(tmp_path, retention_days=-1) == []


def test_retention_deletes_files_older_than_cutoff(tmp_path):
    old_file = tmp_path / "antiga.wav"
    new_file = tmp_path / "nova.wav"
    _touch(old_file, mtime_offset=-40 * 86400)   # 40 dias atrás
    _touch(new_file, mtime_offset=-1 * 86400)    # 1 dia atrás

    deleted = delete_expired_recordings(tmp_path, retention_days=30)

    assert deleted == ["antiga.wav"]
    assert not old_file.exists()
    assert new_file.exists()


def test_retention_ignores_non_audio_files(tmp_path):
    old_txt = tmp_path / "notas.txt"
    _touch(old_txt, mtime_offset=-999999)

    deleted = delete_expired_recordings(tmp_path, retention_days=1)
    assert deleted == []
    assert old_txt.exists()


def test_retention_on_missing_directory_returns_empty(tmp_path):
    assert delete_expired_recordings(tmp_path / "nao-existe", retention_days=30) == []


def test_retention_does_not_follow_symlinked_root_or_parent(tmp_path):
    actual = tmp_path / "real"
    actual.mkdir()
    old = actual / "pessoa-5511999999999.wav"
    _touch(old, mtime_offset=-40 * 86400)
    root_link = tmp_path / "root-link"
    root_link.symlink_to(actual, target_is_directory=True)
    parent = tmp_path / "parent"
    parent.mkdir()
    parent_link = parent / "nested"
    parent_link.symlink_to(actual, target_is_directory=True)
    assert delete_expired_recordings(root_link, 30) == []
    assert delete_expired_recordings(parent_link, 30) == []
    assert old.exists()
    assert delete_expired_recordings(actual, 30) == [old.name]


def test_retention_ignores_symlinked_audio_special_files_and_malformed_names(tmp_path):
    outside = tmp_path.parent / "not-in-recordings-retention.wav"
    _touch(outside, mtime_offset=-40 * 86400)
    folder = tmp_path / "monitor"
    folder.mkdir()
    (folder / "linked.wav").symlink_to(outside)
    (folder / "directory.wav").mkdir()
    bad = folder / "bad\nname.wav"
    _touch(bad, mtime_offset=-40 * 86400)
    fifo = folder / "pipe.wav"
    if hasattr(os, "mkfifo"):
        os.mkfifo(fifo)
    old = folder / "regular.wav"
    _touch(old, mtime_offset=-40 * 86400)
    assert delete_expired_recordings(folder, 30) == ["regular.wav"]
    assert outside.exists()
    assert (folder / "linked.wav").is_symlink()
    assert bad.exists()
    assert (folder / "directory.wav").is_dir()
    if hasattr(os, "mkfifo"):
        assert fifo.exists()


def test_retention_fails_closed_on_invalid_types_and_clock(tmp_path):
    old = tmp_path / "old.wav"
    _touch(old, mtime_offset=-40 * 86400)
    for duration in (None, False, 30.0, "30", {}, -1, 0):
        assert delete_expired_recordings(tmp_path, duration) == []
    for now in (None, "2026", False, float("nan"), float("inf")):
        assert delete_expired_recordings(tmp_path, 30, clock=lambda x=now: x) == []
    assert old.exists()
