"""AXE PABX puro: 1.000 arquivos temporários, retenção e limite temporal."""
import os
import pytest
from retention import delete_old_backups,list_backups

NOW=1_800_000_000
DAY=86_400

@pytest.mark.parametrize("case",[pytest.param(i,id=f"AXE-{i+9001:05d}") for i in range(1000)])
def test_1000_distinct_backup_artifacts_and_retention_boundaries(case,tmp_path):
    file=tmp_path/f"pabx-config-{case:04d}.tar.gz"
    file.write_bytes(f"backup-{case:04d}".encode())
    age=(case+1)*100 if case<500 else 30*DAY+case+1
    mtime=NOW-age
    os.utime(file,(mtime,mtime))
    assert list_backups(tmp_path)==[file.name]
    deleted=delete_old_backups(tmp_path,30,clock=lambda:NOW)
    if case<500:
        assert deleted==[] and file.exists()
    else:
        assert deleted==[file.name] and not file.exists()
    assert list_backups(tmp_path)==([file.name] if case<500 else [])
