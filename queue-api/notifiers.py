"""
Notificações de chamada perdida. Separado em duas partes de propósito:

1. build_email_message / build_whatsapp_payload - lógica PURA de
   montagem de conteúdo, sem rede, 100% testável.
2. send_email / send_whatsapp - fazem a chamada de rede de verdade
   (SMTP / API do WhatsApp). Igual ao ami_client.py, isso só dá pra
   validar contra um servidor SMTP e uma conta do WhatsApp Business
   de verdade - não tem teste automatizado de integração aqui.
"""
import json
import smtplib
import urllib.request
from email.mime.text import MIMEText


def _display_name(missed_call: dict) -> str:
    return missed_call.get("caller_id_name") or missed_call.get("caller_id_num") or "desconhecido"


def build_email_message(missed_call: dict, config: dict):
    """Retorna (subject, body) - texto simples, sem HTML de propósito."""
    caller = _display_name(missed_call)
    subject = f"Chamada perdida de {caller}"

    body_lines = [
        "Você perdeu uma chamada no PABX.",
        "",
        f"De: {caller} ({missed_call.get('caller_id_num', 'desconhecido')})",
        f"Para: {missed_call.get('destination', '')}",
        f"Motivo: {missed_call.get('reason', '')}",
    ]
    return subject, "\n".join(body_lines)


def build_whatsapp_payload(missed_call: dict, config: dict) -> dict:
    """
    Monta o corpo da requisição pra API do WhatsApp Business Cloud
    (Meta). Formato de mensagem de texto simples.
    """
    caller = _display_name(missed_call)
    text = (
        f"Chamada perdida de {caller} ({missed_call.get('caller_id_num', 'desconhecido')}). "
        f"Motivo: {missed_call.get('reason', '')}"
    )
    return {
        "messaging_product": "whatsapp",
        "to": config.get("to_number", ""),
        "type": "text",
        "text": {"body": text},
    }


def send_email(smtp_config: dict, subject: str, body: str):
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = smtp_config["from_addr"]
    msg["To"] = smtp_config["to_addr"]

    with smtplib.SMTP(smtp_config["host"], int(smtp_config.get("port", 587)), timeout=10) as server:
        if smtp_config.get("use_tls", True):
            server.starttls()
        if smtp_config.get("username"):
            server.login(smtp_config["username"], smtp_config["password"])
        server.send_message(msg)


def send_whatsapp(whatsapp_config: dict, payload: dict):
    url = f"https://graph.facebook.com/v19.0/{whatsapp_config['phone_number_id']}/messages"
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {whatsapp_config['access_token']}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status


def dispatch_notifications(missed_call: dict, notify_config: dict):
    """
    Envia a notificação pelos canais habilitados em
    notify_config["channels"] (lista, ex: ["email", "whatsapp"]).
    Cada canal falha de forma isolada - um erro no WhatsApp não deve
    impedir o email de ser enviado, e vice-versa.
    """
    channels = notify_config.get("channels", [])
    errors = []

    if "email" in channels and notify_config.get("smtp"):
        try:
            subject, body = build_email_message(missed_call, notify_config)
            send_email(notify_config["smtp"], subject, body)
        except Exception as exc:  # noqa: BLE001 - queremos capturar qualquer falha de rede/config
            errors.append(f"email: {exc}")

    if "whatsapp" in channels and notify_config.get("whatsapp"):
        try:
            payload = build_whatsapp_payload(missed_call, notify_config["whatsapp"])
            send_whatsapp(notify_config["whatsapp"], payload)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"whatsapp: {exc}")

    return errors
