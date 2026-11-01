"""REL-17: teste de restauração real de arquivos em diretório isolado.

Nunca acessa volumes Docker nem o diretório operacional do PABX.
"""
import io
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESTORE = ROOT / "backup/restore.sh"
DIRS = ("asterisk", "admin", "webphone", "provisioning", "recordings", "admin_data", "queue_api_data")
FILES = ("docker-compose.yml", "prompt-base-pabx.md")


def make_archive(path):
    with tarfile.open(path, "w:gz") as archive:
        for folder in DIRS:
            info = tarfile.TarInfo(f"pabx/{folder}/")
            info.type = tarfile.DIRTYPE
            info.mode = 0o755
            archive.addfile(info)
            data = b"previous-release"
            info = tarfile.TarInfo(f"pabx/{folder}/release-marker.txt")
            info.size = len(data)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(data))
        for filename in FILES:
            data = b"previous-release"
            info = tarfile.TarInfo(f"pabx/{filename}")
            info.size = len(data)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(data))


def test_rollback_restaura_versao_anterior_em_sandbox(tmp_path):
    for folder in DIRS:
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "release-marker.txt").write_bytes(b"new-release")
    for filename in FILES:
        (tmp_path / filename).write_bytes(b"new-release")
    archive = tmp_path / "snapshot.tar.gz"
    make_archive(archive)
    result = subprocess.run(
        ["sh", str(RESTORE), str(archive)],
        input="sim\n", text=True, cwd=tmp_path,
        capture_output=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stderr
    for folder in DIRS:
        assert (tmp_path / folder / "release-marker.txt").read_bytes() == b"previous-release"
    for filename in FILES:
        assert (tmp_path / filename).read_bytes() == b"previous-release"
    assert "FALTA UM PASSO MANUAL" in result.stdout


def test_rollback_sem_confirmacao_preserva_versao_atual(tmp_path):
    for folder in DIRS:
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "release-marker.txt").write_bytes(b"new-release")
    archive = tmp_path / "snapshot.tar.gz"
    make_archive(archive)
    result = subprocess.run(
        ["sh", str(RESTORE), str(archive)],
        input="nao\n", text=True, cwd=tmp_path,
        capture_output=True, timeout=20, check=False,
    )
    assert result.returncode != 0
    for folder in DIRS:
        assert (tmp_path / folder / "release-marker.txt").read_bytes() == b"new-release"
