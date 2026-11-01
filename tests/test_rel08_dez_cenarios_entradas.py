"""Dez cenários independentes de entrada da política externa.

Testes estáticos/modelo: não simulam execução SIP/Asterisk real.
"""
from pathlib import Path
import re

import pytest

POLICY = (Path(__file__).resolve().parents[1] / "asterisk" / "dialplan_politica_externa.conf").read_text(encoding="utf-8")
CONTEXT = POLICY.split("[politica-externa]", 1)[1]

# Os padrões reproduzem a gramática declarada no dialplan; as assertivas
# de ligação abaixo evitam que a simulação se descole da configuração.
TENANT = re.compile(r"^t[0-9]+$")
DESTINO = re.compile(r"^[0-9]+$")


@pytest.mark.parametrize(
    ("tenant", "destino", "bloqueio_internacional", "esperado"),
    [
        ("t1", "0011442070000000", True, "DENY"),   # 01: t1 internacional bloqueado
        ("t2", "0011442070000000", False, "ALLOW"),  # 02: t2 independente
        ("t1", "5511999999999", True, "ALLOW"),     # 03: nacional permitido
        ("t1", "", False, "DENY"),                  # 04: destino vazio
        ("", "1234", False, "DENY"),                # 05: tenant vazio
        ("t1/../t2", "1234", False, "DENY"),        # 06: tenant com path
        ("t1;Dial", "1234", False, "DENY"),         # 07: tenant com comando
        ("t1", "+5511999999999", False, "DENY"),    # 08: destino com sinal +
        ("t1", "123;Dial", False, "DENY"),          # 09: destino com comando
        ("t1", "00 11442070000000", False, "DENY"), # 10: destino com espaço
    ],
)
def test_dez_cenarios_politica_externa(tenant, destino, bloqueio_internacional, esperado):
    assert 'REGEX("^t[0-9]+$" ${TENANT})' in CONTEXT
    assert 'REGEX("^[0-9]+$" ${DESTINO})' in CONTEXT
    assert 'DESTINO:0:2' in CONTEXT
    assert 'DB(politica-externa-${TENANT}/internacional)' in CONTEXT
    assert CONTEXT.index('Set(GOSUB_RETVAL=DENY)') < CONTEXT.index('Set(GOSUB_RETVAL=ALLOW)')
    if not TENANT.fullmatch(tenant) or not DESTINO.fullmatch(destino):
        decisao = "DENY"
    elif destino.startswith("00") and bloqueio_internacional:
        decisao = "DENY"
    else:
        decisao = "ALLOW"
    assert decisao == esperado
