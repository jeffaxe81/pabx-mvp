from notifiers import build_email_message, build_whatsapp_payload

def test_multiline_ami_fields_never_enter_email():
    data = {"caller_id_num":"123", "caller_id_name":"Cliente", "destination":"1000\nCc: attacker", "reason":"NOANSWER\nInjected"}
    subject, body = build_email_message(data, {})
    assert "attacker" not in body and "Injected" not in body
    assert "Cliente" in subject and "123" in body

def test_multiline_ami_fields_never_enter_whatsapp():
    data = {"caller_id_num":"123\nInjected", "caller_id_name":"Nome", "reason":"BUSY\rFake"}
    payload = build_whatsapp_payload(data, {"to_number":"5511900000000"})
    assert "Injected" not in payload["text"]["body"]
    assert "Fake" not in payload["text"]["body"]
    assert "desconhecido" in payload["text"]["body"]
