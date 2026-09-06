#!/usr/bin/env python3
"""
Script chamado pelo Asterisk (mailcmd em voicemail.conf) toda vez que
uma nova mensagem de voz chega. O Asterisk já monta o e-mail completo
(cabeçalhos + anexo de áudio, por causa de attach=yes) e manda pelo
stdin - este script só precisa repassar isso pra um servidor SMTP de
verdade, porque o container do Asterisk não tem um MTA (sendmail/
postfix) configurado.

Lógica pura (parsing do e-mail, checagem de configuração) separada do
envio de rede, pro mesmo padrão de testabilidade usado no resto do
projeto (ver queue-api/notifiers.py).
"""
import email
import os
import smtplib
import sys


def parse_stdin_email(raw_bytes: bytes):
    """Parseia o e-mail que o Asterisk gerou (RFC822) a partir do stdin."""
    return email.message_from_bytes(raw_bytes)


def extract_recipient(msg) -> str:
    """Extrai o endereço de destino do cabeçalho 'To' do e-mail."""
    return msg.get("To", "")


def is_configured(smtp_host: str) -> bool:
    """Desligado por padrão - só envia se um host SMTP foi configurado."""
    return bool(smtp_host)


def send_email_via_smtp(msg, smtp_config: dict):
    with smtplib.SMTP(smtp_config["host"], int(smtp_config.get("port", 587)), timeout=10) as server:
        if smtp_config.get("use_tls", True):
            server.starttls()
        if smtp_config.get("username"):
            server.login(smtp_config["username"], smtp_config["password"])
        server.send_message(msg)


def main():
    smtp_config = {
        "host": os.environ.get("SMTP_HOST", ""),
        "port": os.environ.get("SMTP_PORT", "587"),
        "username": os.environ.get("SMTP_USERNAME", ""),
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "use_tls": os.environ.get("SMTP_USE_TLS", "true").lower() == "true",
    }

    if not is_configured(smtp_config["host"]):
        # Desligado por padrão - sai silenciosamente, sem travar o
        # Asterisk nem gerar erro no log da mensagem de voz.
        return

    raw_bytes = sys.stdin.buffer.read()
    msg = parse_stdin_email(raw_bytes)

    try:
        send_email_via_smtp(msg, smtp_config)
    except Exception as exc:  # noqa: BLE001
        recipient = extract_recipient(msg)
        print(f"[AVISO] falha ao enviar e-mail de correio de voz pra {recipient}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
