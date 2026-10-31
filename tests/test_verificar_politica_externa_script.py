"""Testes isolados do preflight Asterisk sem alterar a AstDB."""
from pathlib import Path
import os
import subprocess

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verificar-politica-externa.sh"


def _run(tmp_path, missing=None):
    fake = tmp_path / "asterisk"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        "case \"$2\" in\n"
        "  'dialplan show politica-externa') echo '[politica-externa]' ;;\n"
        "  'dialplan show t1-internal') echo '[t1-internal]' ;;\n"
        "  'dialplan show t2-internal') echo '[t2-internal]' ;;\n"
        "  'database get politica-externa-t1 internacional') echo 'Value: bloquear' ;;\n"
        "  'database get politica-externa-t2 internacional') echo 'Database entry not found.' ;;\n"
        "  *) exit 1 ;;\n"
        "esac\n"
    )
    if missing:
        data = fake.read_text().replace(f"echo '[{missing}]'", "echo 'contexto ausente'")
        fake.write_text(data)
    fake.chmod(0o755)
    return subprocess.run(
        ["bash", str(SCRIPT)], env={**os.environ, "ASTERISK_BIN": str(fake)},
        text=True, capture_output=True, check=False, timeout=10
    )


def test_preflight_contextos_presentes_e_consulta_astdb(tmp_path):
    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "OK contexto politica-externa" in result.stdout
    assert "OK contexto t1-internal" in result.stdout
    assert "OK contexto t2-internal" in result.stdout
    assert "Value: bloquear" in result.stdout
    assert "PENDENTE: executar chamadas SIP reais" in result.stdout


def test_preflight_falha_se_contexto_ausente(tmp_path):
    result = _run(tmp_path, missing="t2-internal")
    assert result.returncode == 1
    assert "contexto t2-internal ausente" in result.stderr
    assert "Pre-requisitos consultados" not in result.stdout
