"""
Validação do pickup dirigido (POST /api/queue/pickup). Lógica pura,
separada do server.py pra ficar testável sem HTTP.

Com múltiplas telefonistas (backlog #8), o pickup precisa saber QUAL
ramal está pedindo pra puxar a chamada - não existe mais um único
alvo fixo. A extensão é validada contra uma allowlist, no mesmo
padrão já usado pelo click-to-call.
"""


def validate_pickup_request(data: dict, config: dict):
    """
    Retorna (ok, error_message, channel, extension). Se ok=False,
    channel e extension vêm None.
    """
    channel = data.get("channel")
    if not channel:
        return False, "campo 'channel' obrigatório", None, None

    extension = data.get("extension")
    allowed_extensions = config.get("allowed_extensions", [])
    if not extension or extension not in allowed_extensions:
        return False, f"ramal '{extension}' não autorizado para pickup", None, None

    return True, None, channel, extension


# A fila observada vem do AMI (fonte confiável), jamais do JSON HTTP.
# Compara o ID inteiro: t1 e t10 não são intercambiáveis.
import re

_PICKUP_EXTENSION = re.compile(r"^(t[1-9][0-9]*)-[a-z0-9][a-z0-9_-]{0,79}$")
_TENANT_QUEUE = re.compile(r"^fila-(t[1-9][0-9]*)(?:-(?:en|es))?$")


def pickup_matches_queue(extension, queue_name):
    """Exige vínculo exato entre ramal autorizado e fila AMI observada."""
    if not isinstance(extension, str) or not isinstance(queue_name, str):
        return False
    owner = _PICKUP_EXTENSION.fullmatch(extension)
    queue = _TENANT_QUEUE.fullmatch(queue_name)
    return owner is not None and queue is not None and owner.group(1) == queue.group(1)
