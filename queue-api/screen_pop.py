"""
Screen-pop pro CRM (PABX -> CRM, direção oposta ao click-to-call do
manual 12). Quando uma chamada começa a tocar num ramal, o CRM pode
ser avisado via webhook pra abrir o cadastro do cliente
automaticamente.

Fonte do evento: AMI "DialBegin" (início de um Dial()) - dá o
CallerID de quem está ligando e o destino, antes mesmo de ser
atendida. Lógica pura de parsing/montagem aqui; o envio de rede fica
isolado (mesma separação já usada em notifiers.py).
"""
import json
import urllib.request


def parse_dial_begin_event(event: dict):
    """
    Extrai os dados relevantes de um evento AMI 'DialBegin', ou
    retorna None se o evento não servir (não é DialBegin, ou sem
    CallerID).
    """
    if event.get("Event") != "DialBegin":
        return None

    caller_id_num = event.get("CallerIDNum")
    if not caller_id_num:
        return None

    return {
        "caller_id_num": caller_id_num,
        "caller_id_name": event.get("CallerIDName", ""),
        "destination_exten": event.get("DestExten", ""),
        "destination_channel": event.get("DestChannel", ""),
    }


def build_webhook_payload(call_info: dict) -> dict:
    return {
        "event": "incoming_call",
        "caller_number": call_info["caller_id_num"],
        "caller_name": call_info.get("caller_id_name", ""),
        "operator_extension": call_info.get("destination_exten", ""),
    }


def send_webhook(url: str, payload: dict, timeout=5):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status


def dispatch_screen_pop(event: dict, webhook_url: str):
    """
    Ponto único chamado pelo server.py: se o evento for um DialBegin
    válido e houver uma URL de webhook configurada, monta e envia.
    Retorna uma mensagem de erro (string) em caso de falha, ou None.
    """
    if not webhook_url:
        return None

    call_info = parse_dial_begin_event(event)
    if not call_info:
        return None

    try:
        send_webhook(webhook_url, build_webhook_payload(call_info))
        return None
    except Exception as exc:  # noqa: BLE001
        return f"screen-pop: {exc}"
