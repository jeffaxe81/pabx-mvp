import os
import time
from retention import delete_old_backups, list_backups

def test_symlink_file_is_never_deleted(tmp_path):
    original = tmp_path / "keep.dat"
    original.write_text("x")
    link = tmp_path / "alias.tar.gz"
    link.symlink_to(original)
    assert delete_old_backups(tmp_path, 1) == []
    assert list_backups(tmp_path) == []
    assert link.is_symlink()

def test_symlink_directory_is_ignored(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    old = real / "old.tar.gz"
    old.write_text("x")
    os.utime(old, (time.time()-86400*40,)*2)
    link = tmp_path / "alias"
    link.symlink_to(real, target_is_directory=True)
    assert delete_old_backups(link, 1) == []
    assert old.exists()
