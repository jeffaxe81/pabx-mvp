"""
Testes estáticos do asterisk/voicemail.conf.
"""
from pathlib import Path

VOICEMAIL_CONF = Path(__file__).parent.parent / "asterisk" / "voicemail.conf"


def test_tenant_1_mailboxes_present():
    content = VOICEMAIL_CONF.read_text(encoding="utf-8")
    assert "[t1]" in content
    assert "t1-1001 => 1234" in content


def test_voicemail_email_relay_configured():
    """
    Sem mailcmd/serveremail, o Asterisk tentaria usar sendmail direto
    (que não existe no container) e a mensagem de voz nunca chegaria
    por e-mail, silenciosamente.
    """
    content = VOICEMAIL_CONF.read_text(encoding="utf-8")
    assert "serveremail=" in content
    assert "mailcmd=" in content
    assert "mail_relay.py" in content


def test_includes_admin_panel_dynamic_mailboxes():
    """
    Sem esse #include, ramais criados pelo painel de administração
    (backlog #10) não têm caixa de voz, mesmo que o resto (SIP,
    dialplan) funcione.
    """
    content = VOICEMAIL_CONF.read_text(encoding="utf-8")
    assert "#include voicemail_dynamic_t1.conf" in content
