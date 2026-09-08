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


# ---------- is_safe_sound_filename (backlog #60) ----------

def test_accepts_valid_filename():
    from sounds import is_safe_sound_filename
    assert is_safe_sound_filename("menu-principal-pt.wav") is True
    assert is_safe_sound_filename("tts-abc123.wav") is True


def test_rejects_path_traversal_attempts():
    from sounds import is_safe_sound_filename
    for bad in ("../../etc/passwd", "../secrets.wav", "..%2f..%2fetc%2fpasswd.wav"):
        assert is_safe_sound_filename(bad) is False, f"'{bad}' deveria ser rejeitado"


def test_rejects_path_separators():
    from sounds import is_safe_sound_filename
    assert is_safe_sound_filename("subpasta/arquivo.wav") is False
    assert is_safe_sound_filename("subpasta\\arquivo.wav") is False


def test_rejects_non_wav_extension():
    from sounds import is_safe_sound_filename
    assert is_safe_sound_filename("script.sh") is False
    assert is_safe_sound_filename("audio.mp3") is False


def test_rejects_uppercase_and_special_characters():
    from sounds import is_safe_sound_filename
    assert is_safe_sound_filename("MENU.wav") is False
    assert is_safe_sound_filename("menu principal.wav") is False
    assert is_safe_sound_filename("menu;rm-rf.wav") is False


def test_rejects_empty_or_none():
    from sounds import is_safe_sound_filename
    assert is_safe_sound_filename("") is False
    assert is_safe_sound_filename(None) is False
