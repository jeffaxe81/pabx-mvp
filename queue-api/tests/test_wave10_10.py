from unittest.mock import patch
from notifiers import dispatch_notifications

def test_notifier_error_never_echoes_credential_from_exception():
    config = {"channels":["email","whatsapp"],
              "smtp":{"host":"smtp.example"},
              "whatsapp":{"access_token":"SECRET-TOKEN"}}
    with patch("notifiers.send_email", side_effect=RuntimeError("SECRET-TOKEN smtp")), \
         patch("notifiers.send_whatsapp", side_effect=RuntimeError("SECRET-TOKEN whatsapp")):
        errors = dispatch_notifications({"caller_id_num":"123"}, config)
    assert len(errors) == 2
    assert errors == ["email: falha no envio", "whatsapp: falha no envio"]
    assert "SECRET-TOKEN" not in str(errors)
