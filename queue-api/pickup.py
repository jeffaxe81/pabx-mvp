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
