"""REL-17: recuperação integral e reversão de rollback em sandbox isolada."""
import io
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "backup" / "restore_sandbox.py"
DIRS = ("asterisk", "admin", "webphone", "provisioning",
        "recordings", "admin_data", "queue_api_data")
FILES = ("docker-compose.yml", "prompt-base-pabx.md")


def snapshot(path, invalid=False):
    with tarfile.open(path, "w:gz") as archive:
        for folder in DIRS:
            info = tarfile.TarInfo("pabx/" + folder + "/")
            info.type = tarfile.DIRTYPE
            archive.addfile(info)
            data = (folder + "-versao-antiga").encode()
            fileinfo = tarfile.TarInfo("pabx/" + folder + "/state.txt")
            fileinfo.size = len(data)
            archive.addfile(fileinfo, io.BytesIO(data))
        for filename in FILES:
            if invalid and filename == "prompt-base-pabx.md":
                continue
            data = (filename + "-versao-antiga").encode()
            info = tarfile.TarInfo("pabx/" + filename)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))


def populated_sandbox(tmp_path):
    target = tmp_path / "dest"
    target.mkdir()
    (target / ".axe-pabx-sandbox").write_text("local-test")
    for folder in DIRS:
        dest = target / folder
        dest.mkdir()
        (dest / "state.txt").write_text("versao-nova")
        (dest / "arquivo-orfao.txt").write_text("nao-pode-sobrar")
    for filename in FILES:
        (target / filename).write_text("versao-nova")
    return target


def run(archive, target):
    return subprocess.run([sys.executable, str(SCRIPT), str(archive),
                           "--sandbox-root", str(target)],
                          capture_output=True, text=True, timeout=30)


def test_rollback_integral_inclui_volumes_e_remove_orfaos(tmp_path):
    target = populated_sandbox(tmp_path)
    archive = tmp_path / "snapshot.tar.gz"
    snapshot(archive)
    result = run(archive, target)
    assert result.returncode == 0, result.stderr
    for folder in DIRS:
        assert (target / folder / "state.txt").read_text() == folder + "-versao-antiga"
        assert not (target / folder / "arquivo-orfao.txt").exists()
    for filename in FILES:
        assert (target / filename).read_text() == filename + "-versao-antiga"
    assert (target / ".axe-pabx-sandbox").exists()


def test_snapshot_incompleto_nao_toca_versao_atual(tmp_path):
    target = populated_sandbox(tmp_path)
    archive = tmp_path / "incompleto.tar.gz"
    snapshot(archive, invalid=True)
    result = run(archive, target)
    assert result.returncode != 0
    for folder in DIRS:
        assert (target / folder / "state.txt").read_text() == "versao-nova"
    for filename in FILES:
        assert (target / filename).read_text() == "versao-nova"


def test_nao_executa_em_raiz_sem_marcador(tmp_path):
    target = populated_sandbox(tmp_path)
    (target / ".axe-pabx-sandbox").unlink()
    archive = tmp_path / "snapshot.tar.gz"
    snapshot(archive)
    result = run(archive, target)
    assert result.returncode != 0
    assert (target / "asterisk" / "state.txt").read_text() == "versao-nova"
