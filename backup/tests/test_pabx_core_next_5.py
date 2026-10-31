"""Backup retention and inventory must not follow symbolic directory ancestors."""
import os
from retention import delete_old_backups, list_backups

def test_backup_inventory_refuses_symlinked_directory(tmp_path):
    actual=tmp_path/"actual"
    actual.mkdir()
    (actual/"pabx-old.tar.gz").write_bytes(b"example")
    link=tmp_path/"shortcut"
    link.symlink_to(actual, target_is_directory=True)
    assert list_backups(link)==[]

def test_backup_inventory_refuses_non_directory(tmp_path):
    target=tmp_path/"file.tar.gz"
    target.write_bytes(b"example")
    assert list_backups(target)==[]

def test_backup_inventory_refuses_symlink_ancestor(tmp_path):
    actual=tmp_path/"actual"
    (actual/"backups").mkdir(parents=True)
    (actual/"backups"/"pabx-old.tar.gz").write_bytes(b"example")
    link=tmp_path/"shortcut"
    link.symlink_to(actual, target_is_directory=True)
    assert list_backups(link/"backups")==[]

def test_backup_retention_never_deletes_archive_through_symlink_ancestor(tmp_path):
    actual=tmp_path/"actual"
    (actual/"backups").mkdir(parents=True)
    target=actual/"backups"/"pabx-old.tar.gz"
    target.write_bytes(b"example")
    os.utime(target,(100,100))
    link=tmp_path/"shortcut"
    link.symlink_to(actual, target_is_directory=True)
    assert delete_old_backups(link/"backups",30,clock=lambda:1_800_000_000)==[]
    assert target.exists()

def test_backup_direct_directory_still_lists_archives(tmp_path):
    file=tmp_path/"pabx-old.tar.gz"
    file.write_bytes(b"example")
    assert list_backups(tmp_path)==[file.name]
