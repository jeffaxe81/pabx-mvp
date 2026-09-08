import time

from sounds import list_sound_files


def test_lists_wav_files_with_metadata(tmp_path):
    (tmp_path / "menu-principal-pt.wav").write_bytes(b"conteudo-fake")

    entries = list_sound_files(tmp_path)
    assert len(entries) == 1
    assert entries[0]["filename"] == "menu-principal-pt.wav"
    assert entries[0]["size_bytes"] == len(b"conteudo-fake")
    assert entries[0]["modified_at"] > 0


def test_ignores_non_wav_files(tmp_path):
    (tmp_path / "audio.wav").write_bytes(b"x")
    (tmp_path / "notas.txt").write_text("nao e audio")
    (tmp_path / ".gitkeep").write_text("")

    entries = list_sound_files(tmp_path)
    filenames = [e["filename"] for e in entries]
    assert filenames == ["audio.wav"]


def test_returns_empty_list_for_missing_directory(tmp_path):
    assert list_sound_files(tmp_path / "nao-existe") == []


def test_returns_empty_list_for_empty_directory(tmp_path):
    assert list_sound_files(tmp_path) == []


def test_sorted_newest_first(tmp_path):
    old_file = tmp_path / "antigo.wav"
    old_file.write_bytes(b"x")
    time.sleep(0.01)
    new_file = tmp_path / "novo.wav"
    new_file.write_bytes(b"x")

    entries = list_sound_files(tmp_path)
    assert [e["filename"] for e in entries] == ["novo.wav", "antigo.wav"]
