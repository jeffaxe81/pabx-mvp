from sounds import list_sound_files

def test_audio_list_rejects_directory_symlink(tmp_path):
    real = tmp_path / "private"
    real.mkdir()
    (real / "menu.wav").write_bytes(b"data")
    link = tmp_path / "audios"
    link.symlink_to(real, target_is_directory=True)
    assert list_sound_files(link) == []
    assert [r["filename"] for r in list_sound_files(real)] == ["menu.wav"]

def test_audio_list_skips_missing_directory(tmp_path):
    assert list_sound_files(tmp_path / "missing") == []
