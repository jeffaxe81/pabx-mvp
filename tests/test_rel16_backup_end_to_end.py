"""REL-16: gerar e recuperar snapshot completo em sandbox sem Docker real."""
import os
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRS = ("asterisk", "admin", "webphone", "provisioning", "recordings", "admin_data", "queue_api_data")
FILES = ("docker-compose.yml", "prompt-base-pabx.md")


def test_backup_gerado_validado_e_recuperado_em_sandbox(tmp_path):
    source = tmp_path / "source"
    pabx = source / "pabx"
    pabx.mkdir(parents=True)
    for name in DIRS:
        directory = pabx / name
        directory.mkdir()
        (directory / "proof.txt").write_text(f"conteudo-{name}", encoding="utf-8")
    for name in FILES:
        (pabx / name).write_text(f"conteudo-{name}", encoding="utf-8")
    backups = tmp_path / "backups"
    backups.mkdir()
    env = dict(os.environ)
    env.update({
        "PABX_BACKUP_SOURCE_ROOT": str(source),
        "PABX_BACKUP_DEST_DIR": str(backups),
        "PABX_BACKUP_VALIDATOR": str(ROOT / "backup/validate_archive.py"),
        "PABX_BACKUP_RETENTION": str(ROOT / "backup/retention.py"),
        "BACKUP_RETENTION_DAYS": "0",
    })
    result = subprocess.run(["sh", str(ROOT / "backup/backup.sh")],
                            env=env, text=True, capture_output=True,
                            timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    archives = list(backups.glob("*.tar.gz"))
    assert len(archives) == 1
    assert not list(backups.glob("*.partial.*"))
    restored = tmp_path / "restored"
    restored.mkdir()
    with tarfile.open(archives[0], "r:gz") as archive:
        archive.extractall(restored, filter="data")
    for name in DIRS:
        assert (restored / "pabx" / name / "proof.txt").read_text() == f"conteudo-{name}"
    for name in FILES:
        assert (restored / "pabx" / name).read_text() == f"conteudo-{name}"


def test_backup_incompleto_nao_e_publicado(tmp_path):
    source = tmp_path / "source"
    (source / "pabx").mkdir(parents=True)
    backups = tmp_path / "backups"
    backups.mkdir()
    env = dict(os.environ)
    env.update({
        "PABX_BACKUP_SOURCE_ROOT": str(source),
        "PABX_BACKUP_DEST_DIR": str(backups),
        "PABX_BACKUP_VALIDATOR": str(ROOT / "backup/validate_archive.py"),
        "PABX_BACKUP_RETENTION": str(ROOT / "backup/retention.py"),
    })
    result = subprocess.run(["sh", str(ROOT / "backup/backup.sh")],
                            env=env, text=True, capture_output=True,
                            timeout=30, check=False)
    assert result.returncode != 0
    assert not list(backups.glob("*.tar.gz"))
    assert not list(backups.glob("*.partial.*"))
