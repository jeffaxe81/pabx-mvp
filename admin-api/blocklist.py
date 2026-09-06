"""
Validação de números pra lista de bloqueio de discagem externa
(backlog #14). Lógica pura - a persistência de verdade fica no AstDB
do próprio Asterisk (família "blocklist"), gerenciada via AMI
(DBPut/DBDel/DBGetTree) no ami_client.py.
"""
import re

NUMBER_RE = re.compile(r"^[0-9]{3,20}$")


def validate_blocklist_number(raw: str):
    """
    Limpa e valida um número pra bloquear (mesma sanitização usada no
    click-to-call: só dígitos, sem formatação). Retorna o número
    limpo, ou None se inválido.
    """
    if not raw or not isinstance(raw, str):
        return None

    digits = re.sub(r"[^0-9]", "", raw.strip())
    return digits if NUMBER_RE.match(digits) else None
