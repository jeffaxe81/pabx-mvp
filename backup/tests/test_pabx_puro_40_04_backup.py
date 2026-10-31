"""Bateria PABX puro #31-40: retenção de backup testada em diretório temporário."""
import os
from retention import delete_old_backups, list_backups

NOW = 1_800_000_000
DAY = 86400


def archive(path, age_seconds):
    path.write_bytes(b"pabx-test-archive")
    when = NOW - age_seconds
    os.utime(path, (when, when))
    return path


def test_31_zero_retention_never_removes_pabx_configuration_backup(tmp_path):
    path = archive(tmp_path/"pabx-backup-old.tar.gz", 90*DAY)
    assert delete_old_backups(tmp_path, 0, clock=lambda: NOW) == []
    assert path.exists()


def test_32_negative_retention_remains_explicitly_disabled(tmp_path):
    path = archive(tmp_path/"pabx-backup-old.tar.gz", 90*DAY)
    assert delete_old_backups(tmp_path, -1, clock=lambda: NOW) == []
    assert path.exists()


def test_33_retention_keeps_archive_at_exact_age_boundary(tmp_path):
    path = archive(tmp_path/"pabx-backup-equal.tar.gz", 30*DAY)
    assert delete_old_backups(tmp_path, 30, clock=lambda: NOW) == []
    assert path.exists()


def test_34_retention_deletes_archive_one_second_beyond_limit(tmp_path):
    path = archive(tmp_path/"pabx-backup-expired.tar.gz", 30*DAY+1)
    assert delete_old_backups(tmp_path, 30, clock=lambda: NOW) == [path.name]
    assert not path.exists()


def test_35_retention_does_not_delete_recent_backup(tmp_path):
    path = archive(tmp_path/"pabx-backup-recent.tar.gz", 1*DAY)
    assert delete_old_backups(tmp_path, 30, clock=lambda: NOW) == []
    assert path.exists()


def test_36_retention_does_not_delete_non_archive_data(tmp_path):
    path = archive(tmp_path/"extensions_store.json", 99*DAY)
    assert delete_old_backups(tmp_path, 30, clock=lambda: NOW) == []
    assert path.exists()


def test_37_retention_ignores_symlinked_archive(tmp_path):
    original = archive(tmp_path/"outside.data", 90*DAY)
    link = tmp_path/"alias.tar.gz"
    link.symlink_to(original)
    assert delete_old_backups(tmp_path, 30, clock=lambda: NOW) == []
    assert link.is_symlink() and original.exists()


def test_38_retention_cannot_follow_symlinked_backup_directory(tmp_path):
    private = tmp_path/"private"
    private.mkdir()
    old = archive(private/"pabx-backup-old.tar.gz", 90*DAY)
    link = tmp_path/"backups"
    link.symlink_to(private, target_is_directory=True)
    assert delete_old_backups(link, 30, clock=lambda: NOW) == []
    assert old.exists()


def test_39_backup_inventory_is_sorted_most_recent_first(tmp_path):
    archive(tmp_path/"old.tar.gz", 15*DAY)
    archive(tmp_path/"new.tar.gz", 1*DAY)
    assert list_backups(tmp_path) == ["new.tar.gz", "old.tar.gz"]


def test_40_inventory_excludes_symlinks_and_nonarchives(tmp_path):
    original = archive(tmp_path/"actual.tar.gz", 2*DAY)
    link = tmp_path/"shortcut.tar.gz"
    link.symlink_to(original)
    archive(tmp_path/"notes.txt", 1*DAY)
    assert list_backups(tmp_path) == ["actual.tar.gz"]
