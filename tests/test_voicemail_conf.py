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


def test_tenant2_telephonist_mailboxes_present():
    """
    Backlog #38 (multi-tenant completo): as telefonistas web do
    tenant 2 (t2-recepcao/t2-recepcao-2, referenciadas em pjsip.conf
    via mailboxes=) precisam ter a caixa de voz de fato registrada
    aqui - senão o MWI (luz de recado) delas nunca funcionaria.
    """
    content = VOICEMAIL_CONF.read_text(encoding="utf-8")
    assert "[t2]" in content
    assert "t2-recepcao => 1234" in content
    assert "t2-recepcao-2 => 1234" in content
    assert "#include voicemail_dynamic_t2.conf" in content


def test_tenant1_telephonist_mailboxes_present():
    """Mesma checagem pro tenant 1 - gap pré-existente fechado junto com o trabalho de multi-tenant."""
    content = VOICEMAIL_CONF.read_text(encoding="utf-8")
    assert "t1-recepcao => 1234" in content
    assert "t1-recepcao-2 => 1234" in content
