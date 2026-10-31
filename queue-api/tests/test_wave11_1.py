from unittest.mock import patch
from screen_pop import dispatch_screen_pop

def test_webhook_exception_does_not_expose_credential():
    event = {"Event": "DialBegin", "CallerIDNum": "5511999999999"}
    with patch("screen_pop.send_webhook", side_effect=RuntimeError("Bearer secret_token")):
        result = dispatch_screen_pop(event, "https://crm.example/webhook")
    assert result == "screen-pop: falha ao notificar CRM"
    assert "secret_token" not in result
