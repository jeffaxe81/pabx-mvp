"""REL-17: preflight não destrutivo do arquivo de rollback."""
import importlib.util
import io
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "backup" / "validate_archive.py"
spec = importlib.util.spec_from_file_location("validate_archive", SCRIPT)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def archive_at(tmp_path, extra=None, omit=None):
    output = tmp_path / "backup.tar.gz"
    names = [n for n in validator.REQUIRED if n != omit]
    if extra:
        names.append(extra)
    with tarfile.open(output, "w:gz") as archive:
        for name in names:
            data = b"test" if not name.endswith("/") else b""
            info = tarfile.TarInfo(name)
            info.type = tarfile.DIRTYPE if name.endswith("/") else tarfile.REGTYPE
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data) if data else None)
    return output


def test_backup_estruturalmente_valido(tmp_path):
    assert validator.validate(archive_at(tmp_path))


@pytest.mark.parametrize("unsafe", ["../escape", "pabx/../../escape", "/etc/passwd"])
def test_rollback_rejeita_caminhos_inseguros(tmp_path, unsafe):
    with pytest.raises(ValueError, match="inseguro"):
        validator.validate(archive_at(tmp_path, extra=unsafe))


def test_rollback_rejeita_arquivo_obrigatorio_ausente(tmp_path):
    with pytest.raises(ValueError, match="obrigatória"):
        validator.validate(archive_at(tmp_path, omit="pabx/docker-compose.yml"))


def test_restore_exige_preflight_antes_da_confirmacao_e_extracao():
    shell = (ROOT / "backup" / "restore.sh").read_text(encoding="utf-8")
    assert shell.index('validate_archive.py') < shell.index('Continuar?')
    assert shell.index('validate_archive.py') < shell.index('tar xzf')
