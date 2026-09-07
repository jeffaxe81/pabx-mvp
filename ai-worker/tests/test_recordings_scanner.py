import os
import time

from recordings_scanner import list_unprocessed_recordings


def _touch(path, mtime_offset=0):
    path.write_text("audio falso")
    if mtime_offset:
        t = time.time() + mtime_offset
        os.utime(path, (t, t))


def test_lists_files_not_in_already_processed(tmp_path):
    _touch(tmp_path / "a.wav")
    _touch(tmp_path / "b.wav")

    result = list_unprocessed_recordings(tmp_path, already_processed={"a.wav"})
    assert result == ["b.wav"]


def test_returns_empty_when_all_processed(tmp_path):
    _touch(tmp_path / "a.wav")
    assert list_unprocessed_recordings(tmp_path, already_processed={"a.wav"}) == []


def test_ignores_non_audio_files(tmp_path):
    _touch(tmp_path / "a.wav")
    _touch(tmp_path / "notas.txt")
    assert list_unprocessed_recordings(tmp_path, already_processed=set()) == ["a.wav"]


def test_orders_oldest_first(tmp_path):
    _touch(tmp_path / "novo.wav", mtime_offset=0)
    _touch(tmp_path / "antigo.wav", mtime_offset=-1000)

    result = list_unprocessed_recordings(tmp_path, already_processed=set())
    assert result == ["antigo.wav", "novo.wav"]


def test_missing_directory_returns_empty():
    assert list_unprocessed_recordings("/caminho/que/nao/existe", set()) == []
