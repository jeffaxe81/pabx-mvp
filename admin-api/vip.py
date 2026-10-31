"""
Clientes VIP (backlog #28: transferência inteligente por regra) -
número de telefone associado a um ramal de destino direto, guardado
no AstDB (família "vip") - o mesmo banco já usado pra lista de
bloqueio (manual 20) e modo feriado da URA (manual 23).

Lógica pura, sem rede - 100% testável.
"""
import re

NUMBER_RE = re.compile(r"^[0-9]{3,20}$")
EXTENSION_RE = re.compile(r"^[0-9]{3,10}$")


def validate_vip_input(data: dict):
    """
    Valida o número do cliente e o ramal de destino. Retorna
    (ok, error_message, cleaned_data).
    """
    if not isinstance(data, dict):
        return False, "dados VIP inválidos", None
    raw_number = data.get("number") or ""
    if not isinstance(raw_number, str) or len(raw_number) > 128:
        return False, "número de telefone inválido", None
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in raw_number):
        return False, "número de telefone inválido", None
    digits = re.sub(r"[^0-9]", "", raw_number.strip())
    if not NUMBER_RE.match(digits):
        return False, "número de telefone inválido", None

    target_extension = data.get("target_extension") or ""
    if not isinstance(target_extension, str):
        return False, "ramal de destino inválido (ex: 1000, 1010)", None
    target_extension = target_extension.strip()
    if not EXTENSION_RE.match(target_extension):
        return False, "ramal de destino inválido (ex: 1000, 1010)", None

    return True, None, {"number": digits, "target_extension": target_extension}
