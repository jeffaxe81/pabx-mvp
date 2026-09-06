import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from mail_relay import parse_stdin_email, extract_recipient, is_configured, send_email_via_smtp

SAMPLE_EMAIL = (
    b"From: pabx@localhost\r\n"
    b"To: t1-1001@example.com\r\n"
    b"Subject: Nova mensagem de voz\r\n"
    b"\r\n"
    b"Voce tem uma nova mensagem de voz.\r\n"
)


def test_parse_stdin_email_extracts_headers():
    msg = parse_stdin_email(SAMPLE_EMAIL)
    assert msg["To"] == "t1-1001@example.com"
    assert msg["Subject"] == "Nova mensagem de voz"


def test_extract_recipient():
    msg = parse_stdin_email(SAMPLE_EMAIL)
    assert extract_recipient(msg) == "t1-1001@example.com"


def test_extract_recipient_returns_empty_string_when_missing():
    msg = parse_stdin_email(b"Subject: sem destinatario\r\n\r\ncorpo\r\n")
    assert extract_recipient(msg) == ""


def test_is_configured_false_when_host_empty():
    assert is_configured("") is False
    assert is_configured(None) is False


def test_is_configured_true_when_host_set():
    assert is_configured("smtp.exemplo.com") is True


def test_send_email_via_smtp_uses_provided_config():
    msg = parse_stdin_email(SAMPLE_EMAIL)
    config = {"host": "smtp.exemplo.com", "port": "587", "username": "user", "password": "pass", "use_tls": True}

    with patch("mail_relay.smtplib.SMTP") as mock_smtp_class:
        mock_server = mock_smtp_class.return_value.__enter__.return_value
        send_email_via_smtp(msg, config)

    mock_smtp_class.assert_called_once_with("smtp.exemplo.com", 587, timeout=10)
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("user", "pass")
    mock_server.send_message.assert_called_once_with(msg)


def test_send_email_via_smtp_skips_login_without_username():
    msg = parse_stdin_email(SAMPLE_EMAIL)
    config = {"host": "smtp.exemplo.com", "port": "25", "use_tls": False}

    with patch("mail_relay.smtplib.SMTP") as mock_smtp_class:
        mock_server = mock_smtp_class.return_value.__enter__.return_value
        send_email_via_smtp(msg, config)

    mock_server.login.assert_not_called()
    mock_server.starttls.assert_not_called()
