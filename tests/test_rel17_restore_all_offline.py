"""REL-17: rollback real dos arquivos e volumes em sandbox offline."""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backup"))
from restore_volume_data import restore

DIRS = ("asterisk", "admin", "webphone", "provisioning", "recordings", "admin_data", "queue_api_data")
FILES = ("docker-compose.yml", "prompt-base-pabx.md")


def test_rollback_de_arquivos_e_dados_de_volumes(tmp_path):
    source = tmp_path / "source"
    pabx = source / "pabx"
    pabx.mkdir(parents=True)
    for name in DIRS:
        (pabx / name).mkdir()
        (pabx / name / "marker.txt").write_text(f"release-anterior-{name}")
    for name in FILES:
        (pabx / name).write_text("release-anterior")
    backups = tmp_path / "backups"
    backups.mkdir()
    env = dict(os.environ, PABX_BACKUP_SOURCE_ROOT=str(source),
               PABX_BACKUP_DEST_DIR=str(backups),
               PABX_BACKUP_VALIDATOR=str(ROOT / "backup/validate_archive.py"),
               PABX_BACKUP_RETENTION=str(ROOT / "backup/retention.py"))
    subprocess.run(["sh", str(ROOT / "backup/backup.sh")], env=env, check=True, capture_output=True, timeout=30)
    archive = next(backups.glob("*.tar.gz"))
    target = tmp_path / "target"
    target.mkdir()
    for name in DIRS[:5]:
        (target / name).mkdir()
        (target / name / "marker.txt").write_text("release-nova")
    for name in FILES:
        (target / name).write_text("release-nova")
    result = subprocess.run(["sh", str(ROOT / "backup/restore.sh"), str(archive)],
                            cwd=target, input="sim\n", text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    for name in DIRS[:5]:
        assert (target / name / "marker.txt").read_text() == f"release-anterior-{name}"
    for name in FILES:
        assert (target / name).read_text() == "release-anterior"
    admin, queue = tmp_path / "volume-admin", tmp_path / "volume-queue"
    admin.mkdir()
    queue.mkdir()
    assert restore(archive, admin, queue)
    assert (admin / "marker.txt").read_text() == "release-anterior-admin_data"
    assert (queue / "marker.txt").read_text() == "release-anterior-queue_api_data"


def test_volume_restore_rejeita_destino_com_dados(tmp_path):
    source = tmp_path / "source"
    (source / "pabx").mkdir(parents=True)
    admin = tmp_path / "admin"
    queue = tmp_path / "queue"
    admin.mkdir()
    queue.mkdir()
    (admin / "sentinel.txt").write_text("nao-apagar")
    try:
        restore(tmp_path / "missing.tar.gz", admin, queue)
    except (OSError, ValueError):
        pass
    assert (admin / "sentinel.txt").read_text() == "nao-apagar"
