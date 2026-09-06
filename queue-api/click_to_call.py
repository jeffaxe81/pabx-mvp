"""
Click-to-call: um CRM externo chama uma API HTTP pra disparar uma
ligação. O Asterisk primeiro liga pro ramal da telefonista, e quando
ela atende, completa a ligação pro número do cliente (Originate com
Context/Exten apontando pro dialplan que disca pra fora).

Tudo aqui é lógica PURA (sanitização, montagem da ação AMI, validação
da requisição) - testável sem rede. O disparo de verdade (ami.send_action)
fica no server.py, junto com o resto da integração AMI já existente.
"""
import re

DEFAULT_TIMEOUT_MS = 30000


def sanitize_phone_number(raw: str):
    """
    Limpa um número recebido de um CRM (que pode vir formatado tipo
    "(11) 99999-8888" ou "+55 11 99999-8888") pra só dígitos, mantendo
    um "+" inicial se houver. Retorna None se não parecer um número
    válido (curto demais, vazio, etc.) - nunca lança exceção.
    """
    if not raw or not isinstance(raw, str):
        return None

    raw = raw.strip()
    has_plus = raw.startswith("+")
    digits = re.sub(r"[^0-9]", "", raw)

    if len(digits) < 8:
        return None

    return ("+" if has_plus else "") + digits


def build_originate_action(channel: str, number: str, context: str, caller_id_name: str = "CRM Click-to-Call", timeout_ms: int = DEFAULT_TIMEOUT_MS):
    """Monta os campos da Action AMI 'Originate' (dict, pronta pra enviar)."""
    return {
        "Action": "Originate",
        "Channel": channel,
        "Context": context,
        "Exten": number,
        "Priority": "1",
        "Async": "true",
        "Timeout": str(timeout_ms),
        "CallerID": f'"{caller_id_name}" <{number}>',
    }


def validate_click_to_call_request(data: dict, api_key: str, config: dict):
    """
    Valida uma requisição de click-to-call ANTES de qualquer chamada
    AMI. Retorna (ok, error_message, extension, sanitized_number).
    Se ok=False, extension e sanitized_number vêm None.
    """
    configured_key = config.get("api_key", "")
    if not configured_key:
        return False, "click-to-call não está configurado (sem API key definida)", None, None

    if not api_key or api_key != configured_key:
        return False, "chave de API inválida", None, None

    extension = data.get("extension")
    allowed_extensions = config.get("allowed_extensions", [])
    if not extension or extension not in allowed_extensions:
        return False, f"ramal '{extension}' não autorizado para click-to-call", None, None

    number = sanitize_phone_number(data.get("number", ""))
    if not number:
        return False, "número inválido", None, None

    return True, None, extension, number
