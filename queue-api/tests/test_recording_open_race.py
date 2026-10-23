"""Regressoes para abertura segura de audios no Linux/Docker."""
import os

import pytest

import recordings


def test_opens_regular_audio_and_returns_real_file_handle(tmp_path):
    folder = tmp_path / "recordings"
    folder.mkdir()
    (folder / "ok.wav").write_bytes(b"RIFF legitimate")
    with recordings.open_recording_file(folder, "ok.wav") as stream:
        assert stream.read() == b"RIFF legitimate"


@pytest.mark.parametrize("filename", [
    "../secret.wav", "sub/ok.wav", "sub\\\\ok.wav",
    ".", "..", "", "ok.txt", "ok.wav\\n",
])
def test_blocks_untrusted_names(tmp_path, filename):
    assert recordings.open_recording_file(tmp_path, filename) is None


def test_blocks_link_to_audio_outside_allowed_volume(tmp_path):
    folder = tmp_path / "recordings"
    folder.mkdir()
    secret = tmp_path / "outside.wav"
    secret.write_bytes(b"outside")
    (folder / "audio.wav").symlink_to(secret)
    assert recordings.open_recording_file(folder, "audio.wav") is None


def test_blocks_symlinked_recordings_directory(tmp_path):
    folder = tmp_path / "real"
    folder.mkdir()
    (folder / "audio.wav").write_bytes(b"outside")
    linked = tmp_path / "linked"
    linked.symlink_to(folder, target_is_directory=True)
    assert recordings.open_recording_file(linked, "audio.wav") is None


def test_denies_symlink_swapped_at_the_exact_open_boundary(tmp_path, monkeypatch):
    folder = tmp_path / "recordings"
    folder.mkdir()
    legitimate = folder / "audio.wav"
    legitimate.write_bytes(b"legitimate")
    secret = tmp_path / "outside.wav"
    secret.write_bytes(b"should never be served")
    original_open = os.open
    exchanged = []

    def swap_on_file_open(path, flags, *args, **kwargs):
        if path == "audio.wav" and kwargs.get("dir_fd") is not None:
            legitimate.unlink()
            legitimate.symlink_to(secret)
            exchanged.append(True)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(recordings.os, "open", swap_on_file_open)
    assert recordings.open_recording_file(folder, "audio.wav") is None
    assert exchanged == [True]


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="Unix only")
def test_special_file_cannot_block_server_or_be_downloaded(tmp_path):
    folder = tmp_path / "recordings"
    folder.mkdir()
    os.mkfifo(folder / "pipe.wav")
    assert recordings.open_recording_file(folder, "pipe.wav") is None
