"""Regressões de metadados de gravação com diretórios ancorados por FD.

Usa somente diretórios temporários; não requer Asterisk ou áudios reais.
"""
import os

import pytest

import recordings


def test_regular_files_keep_order_metadata_and_filters(tmp_path):
    older = tmp_path / "20260101-120000-555-1000.wav"
    newer = tmp_path / "20260102-120000-777-1000.wav"
    older.write_bytes(b"A")
    newer.write_bytes(b"BB")
    os.utime(older, (100, 100))
    os.utime(newer, (200, 200))
    listed = recordings.list_recordings(tmp_path)
    assert [item["filename"] for item in listed] == [newer.name, older.name]
    assert [item["size_bytes"] for item in listed] == [2, 1]
    assert [item["filename"] for item in recordings.list_recordings(
        tmp_path, caller_number="555")] == [older.name]


def test_middle_ancestor_symlink_blocks_list_and_open(tmp_path):
    real = tmp_path / "real"
    folder = real / "voice" / "calls"
    folder.mkdir(parents=True)
    (folder / "call.wav").write_bytes(b"private")
    linked = tmp_path / "alias"
    linked.symlink_to(real, target_is_directory=True)
    outside = linked / "voice" / "calls"
    assert recordings.list_recordings(outside) == []
    assert recordings.open_recording_file(outside, "call.wav") is None
    assert recordings.list_recordings(folder)[0]["filename"] == "call.wav"


def test_parent_traversal_is_not_accepted(tmp_path):
    folder = tmp_path / "safe"
    folder.mkdir()
    (folder / "call.wav").write_bytes(b"private")
    unsafe = str(folder) + "/../safe"
    assert recordings.list_recordings(unsafe) == []
    assert recordings.open_recording_file(unsafe, "call.wav") is None


def test_listing_symlink_swap_does_not_publish_external_metadata(tmp_path, monkeypatch):
    folder = tmp_path / "recordings"
    folder.mkdir()
    sound = folder / "audio.wav"
    sound.write_bytes(b"A")
    private = tmp_path / "private.wav"
    private.write_bytes(b"long private file")
    original_stat = os.stat
    swaps = []

    def swap_before_stat(path, *args, **kwargs):
        if path == "audio.wav" and kwargs.get("dir_fd") is not None:
            sound.unlink()
            sound.symlink_to(private)
            swaps.append(True)
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(recordings.os, "stat", swap_before_stat)
    assert recordings.list_recordings(folder) == []
    assert swaps == [True]


def test_removed_between_scan_and_stat_does_not_abort_listing(tmp_path, monkeypatch):
    folder = tmp_path / "recordings"
    folder.mkdir()
    vanishing = folder / "gone.wav"
    vanishing.write_bytes(b"test")
    original_stat = os.stat
    swaps = []

    def remove_before_stat(path, *args, **kwargs):
        if path == "gone.wav" and kwargs.get("dir_fd") is not None:
            vanishing.unlink()
            swaps.append(True)
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(recordings.os, "stat", remove_before_stat)
    assert recordings.list_recordings(folder) == []
    assert swaps == [True]


def test_listing_never_stats_audio_symlink_even_without_swap(tmp_path):
    root = tmp_path / "recordings"
    root.mkdir()
    external = tmp_path / "external.wav"
    external.write_bytes(b"private data")
    (root / "external.wav").symlink_to(external)
    assert recordings.list_recordings(root) == []


def test_download_retains_anchored_directory_after_ancestor_is_renamed(tmp_path):
    parent = tmp_path / "initial"
    parent.mkdir()
    audio = parent / "audio.wav"
    audio.write_bytes(b"before")
    with recordings.open_recording_file(parent, "audio.wav") as opened:
        parent.rename(tmp_path / "renamed")
        imposter = tmp_path / "initial"
        imposter.mkdir()
        (imposter / "audio.wav").write_bytes(b"after")
        assert opened.read() == b"before"
