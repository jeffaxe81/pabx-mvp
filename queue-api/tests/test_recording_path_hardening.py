from recordings import safe_recording_path, delete_expired_recordings


def test_rejects_nested_paths_even_when_basename_exists(tmp_path):
    (tmp_path / "call.wav").write_bytes(b"audio")
    assert safe_recording_path(tmp_path, "../call.wav") is None
    assert safe_recording_path(tmp_path, "x/call.wav") is None
    assert safe_recording_path(tmp_path, "x\\\\call.wav") is None
    assert safe_recording_path(tmp_path, "call.wav") == (tmp_path / "call.wav").resolve()


def test_retention_never_deletes_symlink(tmp_path):
    target = tmp_path.parent / ("retention-target-" + tmp_path.name + ".wav")
    target.write_bytes(b"audio")
    (tmp_path / "external.wav").symlink_to(target)
    assert delete_expired_recordings(tmp_path, 1, clock=lambda: 999999999999) == []
    assert target.is_file()
