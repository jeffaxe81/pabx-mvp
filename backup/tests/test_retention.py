import os
import time

from retention import delete_old_backups, list_backups


def _touch(path, mtime_offset=0):
    path.write_text("dados falsos de backup")
    if mtime_offset:
        t = time.time() + mtime_offset
        os.utime(path, (t, t))


def test_disabled_by_default_deletes_nothing(tmp_path):
    _touch(tmp_path / "antigo.tar.gz", mtime_offset=-999999)
    deleted = delete_old_backups(tmp_path, retention_days=0)
    assert deleted == []
    assert (tmp_path / "antigo.tar.gz").exists()


def test_negative_days_also_disables(tmp_path):
    _touch(tmp_path / "antigo.tar.gz", mtime_offset=-999999)
    assert delete_old_backups(tmp_path, retention_days=-1) == []


def test_deletes_files_older_than_cutoff(tmp_path):
    old_file = tmp_path / "pabx-backup-antigo.tar.gz"
    new_file = tmp_path / "pabx-backup-novo.tar.gz"
    _touch(old_file, mtime_offset=-40 * 86400)
    _touch(new_file, mtime_offset=-1 * 86400)

    deleted = delete_old_backups(tmp_path, retention_days=30)

    assert deleted == ["pabx-backup-antigo.tar.gz"]
    assert not old_file.exists()
    assert new_file.exists()


def test_ignores_non_backup_files(tmp_path):
    other = tmp_path / "notas.txt"
    _touch(other, mtime_offset=-999999)
    deleted = delete_old_backups(tmp_path, retention_days=1)
    assert deleted == []
    assert other.exists()


def test_missing_directory_returns_empty(tmp_path):
    assert delete_old_backups(tmp_path / "nao-existe", retention_days=30) == []


def test_list_backups_orders_newest_first(tmp_path):
    _touch(tmp_path / "antigo.tar.gz", mtime_offset=-100)
    _touch(tmp_path / "novo.tar.gz", mtime_offset=0)
    assert list_backups(tmp_path) == ["novo.tar.gz", "antigo.tar.gz"]


def test_list_backups_empty_directory(tmp_path):
    assert list_backups(tmp_path) == []
