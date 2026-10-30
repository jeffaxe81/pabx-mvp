from recordings_scanner import list_unprocessed_recordings

def test_scanner_does_not_follow_directory_symlink(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "recording.wav").write_bytes(b"abc")
    link = tmp_path / "alias"
    link.symlink_to(root, target_is_directory=True)
    assert list_unprocessed_recordings(link, set()) == []
    assert list_unprocessed_recordings(root, set()) == ["recording.wav"]

def test_scanner_rejects_non_directory_path(tmp_path):
    f = tmp_path / "audio.wav"
    f.write_bytes(b"RIFF")
    assert list_unprocessed_recordings(f, set()) == []
