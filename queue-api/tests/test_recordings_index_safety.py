"""Regressões de segurança na listagem e no acesso a gravações."""
from recordings import list_recordings, safe_recording_path


def test_listing_ignores_links_to_audio_outside_recordings(tmp_path):
    recordings = tmp_path / "recordings"
    recordings.mkdir()
    external = tmp_path / "private.wav"
    external.write_bytes(b"confidential")
    (recordings / "alias.wav").symlink_to(external)
    (recordings / "legit.wav").write_bytes(b"ok")

    assert [record["filename"] for record in list_recordings(recordings)] == ["legit.wav"]


def test_listing_ignores_symlinks_even_with_filters(tmp_path):
    real = tmp_path / "20260101-120000-5511999998888-1000.wav"
    real.write_bytes(b"outside")
    recordings = tmp_path / "recordings"
    recordings.mkdir()
    (recordings / real.name).symlink_to(real)

    assert list_recordings(recordings, caller_number="5511999998888") == []


def test_streaming_rejects_symlink_alias_even_when_target_is_inside_directory(tmp_path):
    (tmp_path / "real.wav").write_bytes(b"audio")
    (tmp_path / "alias.wav").symlink_to(tmp_path / "real.wav")

    assert safe_recording_path(tmp_path, "alias.wav") is None
    assert safe_recording_path(tmp_path, "real.wav") == (tmp_path / "real.wav").resolve()


def test_zero_and_negative_limit_return_nothing(tmp_path):
    (tmp_path / "real.wav").write_bytes(b"audio")

    assert list_recordings(tmp_path, limit=0) == []
    assert list_recordings(tmp_path, limit=-3) == []


def test_regular_file_as_directory_returns_empty(tmp_path):
    file = tmp_path / "not-a-directory.wav"
    file.write_bytes(b"audio")
    assert list_recordings(file) == []
