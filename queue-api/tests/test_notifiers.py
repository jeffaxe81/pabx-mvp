from unittest.mock import patch

from notifiers import build_email_message, build_whatsapp_payload, dispatch_notifications

SAMPLE_MISSED_CALL = {
    "caller_id_num": "5511988887777",
    "caller_id_name": "Cliente Teste",
    "destination": "1000",
    "reason": "NOANSWER",
    "source": "dial",
}


def test_build_email_message_includes_caller_and_reason():
    subject, body = build_email_message(SAMPLE_MISSED_CALL, {})
    assert "Cliente Teste" in subject
    assert "5511988887777" in body
    assert "NOANSWER" in body
    assert "1000" in body


def test_build_email_message_falls_back_to_number_without_name():
    missed = {**SAMPLE_MISSED_CALL, "caller_id_name": ""}
    subject, _ = build_email_message(missed, {})
    assert "5511988887777" in subject


def test_build_whatsapp_payload_structure():
    payload = build_whatsapp_payload(SAMPLE_MISSED_CALL, {"to_number": "5511900000000"})
    assert payload["messaging_product"] == "whatsapp"
    assert payload["to"] == "5511900000000"
    assert payload["type"] == "text"
    assert "Cliente Teste" in payload["text"]["body"]
    assert "NOANSWER" in payload["text"]["body"]


def test_dispatch_sends_only_enabled_channels():
    config = {
        "channels": ["email"],
        "smtp": {"host": "smtp.example.com", "from_addr": "a@b.com", "to_addr": "c@d.com"},
        "whatsapp": {"phone_number_id": "123", "access_token": "x", "to_number": "555"},
    }

    with patch("notifiers.send_email") as mock_email, patch("notifiers.send_whatsapp") as mock_whatsapp:
        errors = dispatch_notifications(SAMPLE_MISSED_CALL, config)

    mock_email.assert_called_once()
    mock_whatsapp.assert_not_called()
    assert errors == []


def test_dispatch_can_send_both_channels():
    config = {
        "channels": ["email", "whatsapp"],
        "smtp": {"host": "smtp.example.com", "from_addr": "a@b.com", "to_addr": "c@d.com"},
        "whatsapp": {"phone_number_id": "123", "access_token": "x", "to_number": "555"},
    }

    with patch("notifiers.send_email") as mock_email, patch("notifiers.send_whatsapp") as mock_whatsapp:
        errors = dispatch_notifications(SAMPLE_MISSED_CALL, config)

    mock_email.assert_called_once()
    mock_whatsapp.assert_called_once()
    assert errors == []


def test_dispatch_isolates_failures_between_channels():
    """
    Um canal falhando (ex: SMTP fora do ar) não pode impedir o outro
    canal de ser tentado.
    """
    config = {
        "channels": ["email", "whatsapp"],
        "smtp": {"host": "smtp.example.com", "from_addr": "a@b.com", "to_addr": "c@d.com"},
        "whatsapp": {"phone_number_id": "123", "access_token": "x", "to_number": "555"},
    }

    with patch("notifiers.send_email", side_effect=ConnectionError("smtp fora do ar")) as mock_email, \
         patch("notifiers.send_whatsapp") as mock_whatsapp:
        errors = dispatch_notifications(SAMPLE_MISSED_CALL, config)

    mock_email.assert_called_once()
    mock_whatsapp.assert_called_once()  # tentou mesmo com o email falhando
    assert len(errors) == 1
    assert "email" in errors[0]


def test_dispatch_does_nothing_when_no_channels_enabled():
    config = {"channels": []}
    with patch("notifiers.send_email") as mock_email, patch("notifiers.send_whatsapp") as mock_whatsapp:
        errors = dispatch_notifications(SAMPLE_MISSED_CALL, config)

    mock_email.assert_not_called()
    mock_whatsapp.assert_not_called()
    assert errors == []
