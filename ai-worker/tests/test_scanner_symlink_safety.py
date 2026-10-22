from recordings_scanner import list_unprocessed_recordings


def test_scanner_ignores_symlinks_to_external_files(tmp_path):
    external = tmp_path.parent / ("outside-" + tmp_path.name + ".wav")
    external.write_bytes(b"fake wav")
    (tmp_path / "linked.wav").symlink_to(external)
    (tmp_path / "valid.wav").write_bytes(b"audio")
    assert list_unprocessed_recordings(tmp_path, set()) == ["valid.wav"]


def test_scanner_never_reprocesses_known_filename(tmp_path):
    (tmp_path / "valid.wav").write_bytes(b"audio")
    assert list_unprocessed_recordings(tmp_path, {"valid.wav"}) == []
