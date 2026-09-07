from conf_generator import (
    render_pjsip_dynamic, render_extensions_dynamic_dial,
    render_extensions_dynamic_hints, render_voicemail_dynamic, render_all,
)

SAMPLE = [
    {"name": "recepcao-3", "number": 1112, "display_name": "Recepção 3", "password": "senha-forte", "tenant": "t1"},
]


def test_pjsip_dynamic_includes_endpoint_auth_and_aor():
    content = render_pjsip_dynamic(SAMPLE)
    assert "[recepcao-3](endpoint-secure)" in content
    assert "username=recepcao-3" in content
    assert "password=senha-forte" in content
    assert "type=aor" in content
    assert "callerid=Recepção 3 <1112>" in content


def test_pjsip_dynamic_uses_secure_template_not_plain():
    """
    Todo ramal criado pelo painel precisa herdar criptografia -
    nunca deve usar endpoint-plain.
    """
    content = render_pjsip_dynamic(SAMPLE)
    assert "endpoint-plain" not in content
    assert "endpoint-secure" in content


def test_pjsip_dynamic_empty_list_still_has_header_only():
    content = render_pjsip_dynamic([])
    assert "GERADO AUTOMATICAMENTE" in content
    assert "[recepcao" not in content


def test_extensions_dial_includes_mixmonitor_and_dial():
    content = render_extensions_dynamic_dial(SAMPLE)
    assert "exten => 1112,1,MixMonitor(" in content
    assert "Dial(PJSIP/recepcao-3,20)" in content


def test_extensions_hints_reference_correct_endpoint():
    content = render_extensions_dynamic_hints(SAMPLE)
    assert "exten => 1112,hint,PJSIP/recepcao-3" in content


def test_voicemail_dynamic_uses_display_name_and_default_password():
    content = render_voicemail_dynamic(SAMPLE)
    assert "recepcao-3 => 1234,Recepção 3" in content


def test_voicemail_dynamic_includes_email_when_present():
    with_email = [{**SAMPLE[0], "email": "recepcao3@exemplo.com"}]
    content = render_voicemail_dynamic(with_email)
    assert "recepcao-3 => 1234,Recepção 3,recepcao3@exemplo.com" in content


def test_voicemail_dynamic_works_without_email():
    """E-mail é opcional - sem ele, a caixa de voz continua funcionando normalmente."""
    content = render_voicemail_dynamic(SAMPLE)  # SAMPLE não tem campo 'email'
    assert "recepcao-3 => 1234,Recepção 3," in content


def test_render_all_returns_files_per_tenant():
    """
    Backlog #38: dial/hints/voicemail viram um arquivo por tenant
    (t1 e t2) - só pjsip_dynamic.conf continua compartilhado, porque
    cada endpoint já carrega o próprio context= com o tenant certo.
    """
    files = render_all(SAMPLE)
    assert set(files.keys()) == {
        "pjsip_dynamic.conf",
        "extensions_dynamic_dial-t1.conf",
        "extensions_dynamic_dial-t2.conf",
        "extensions_dynamic_hints-t1.conf",
        "extensions_dynamic_hints-t2.conf",
        "voicemail_dynamic_t1.conf",
        "voicemail_dynamic_t2.conf",
    }
    assert all(isinstance(content, str) for content in files.values())


def test_render_all_places_each_extension_in_its_own_tenant_file():
    t2_sample = [{**SAMPLE[0], "name": "vendas-t2-1", "tenant": "t2"}]
    files = render_all(SAMPLE + t2_sample)

    assert "recepcao-3" in files["extensions_dynamic_dial-t1.conf"]
    assert "recepcao-3" not in files["extensions_dynamic_dial-t2.conf"]
    assert "vendas-t2-1" in files["extensions_dynamic_dial-t2.conf"]
    assert "vendas-t2-1" not in files["extensions_dynamic_dial-t1.conf"]


def test_pjsip_dynamic_uses_extension_own_tenant_context():
    """
    Backlog #38: um ramal criado com tenant=t2 precisa gerar
    context=t2-internal - senão o painel só serviria pra criar ramal
    do tenant 1, mesmo aceitando o campo tenant.
    """
    t2_extension = [{**SAMPLE[0], "tenant": "t2"}]
    content = render_pjsip_dynamic(t2_extension)
    assert "context=t2-internal" in content
    assert "subscribe_context=t2-hints" in content
    assert "mailboxes=recepcao-3@t2" in content


def test_multiple_extensions_all_appear():
    two_extensions = SAMPLE + [
        {"name": "vendas-1", "number": 1113, "display_name": "Vendas 1", "password": "outra-senha", "tenant": "t1"}
    ]
    content = render_pjsip_dynamic(two_extensions)
    assert "[recepcao-3]" in content
    assert "[vendas-1]" in content


def test_no_password_leaks_into_hints_or_dial_files():
    """
    Sanity check de segurança básica: os arquivos de dial/hint não
    deveriam conter a senha (só o pjsip_dynamic.conf precisa dela).
    """
    dial = render_extensions_dynamic_dial(SAMPLE)
    hints = render_extensions_dynamic_hints(SAMPLE)
    assert "senha-forte" not in dial
    assert "senha-forte" not in hints
