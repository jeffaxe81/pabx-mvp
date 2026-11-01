"""30 casos de regressao da deteccao de contextos do preflight Asterisk.

Executa o script de verdade contra CLI simulada; nao homologa SIP real.
"""
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verificar-politica-externa.sh"
CONTEXTS = ("politica-externa", "t1-internal", "t2-internal")

# Dez formatos de resposta x tres contextos obrigatorios = 30 casos.
FORMATS = (
    ("cabecalho_simples", "[{ctx}]", True),
    ("cabecalho_real", "[ Context '{ctx}' created by 'pbx_config' ]", True),
    ("cabecalho_real_com_extensao", "[ Context '{ctx}' created by 'pbx_config' ]\n  's' => 1. NoOp()", True),
    ("saida_vazia", "", False),
    ("contexto_diferente", "[outro-contexto]", False),
    ("somente_nome", "{ctx}", False),
    ("nome_no_log", "NOTICE: procurando {ctx}", False),
    ("prefixo_de_contexto", "[{ctx}-extra]", False),
    ("sufixo_de_contexto", "[prefix-{ctx}]", False),
    ("mensagem_erro", "No such context '{ctx}'", False),
)


@pytest.mark.parametrize("contexto", CONTEXTS)
@pytest.mark.parametrize("cenario,formato,valido", FORMATS, ids=[item[0] for item in FORMATS])
def test_contextos_do_preflight_30_cenarios(tmp_path, contexto, cenario, formato, valido):
    fake = tmp_path / "asterisk"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$2" == "dialplan show $MOCK_CONTEXT" ]]; then\n'
        '  printf "%s\\n" "$MOCK_REPLY"\n'
        'elif [[ "$2" == dialplan\\ show\\ * ]]; then\n'
        '  ctx="${2#dialplan show }"\n'
        '  printf "[%s]\\n" "$ctx"\n'
        'elif [[ "$2" == database\\ get\\ * ]]; then\n'
        '  echo "Database entry not found."\n'
        'else\n'
        '  exit 2\n'
        'fi\n'
    )
    fake.chmod(0o755)
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            **os.environ,
            "ASTERISK_BIN": str(fake),
            "MOCK_CONTEXT": contexto,
            "MOCK_REPLY": formato.format(ctx=contexto),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == (0 if valido else 1), (
        contexto, cenario, result.stdout, result.stderr
    )
    if valido:
        assert result.stdout.count("OK contexto ") == 3
    else:
        assert f"contexto {contexto} ausente" in result.stderr
        assert "Pre-requisitos consultados" not in result.stdout
