import os
import time

from recordings import list_recordings, safe_recording_path


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
