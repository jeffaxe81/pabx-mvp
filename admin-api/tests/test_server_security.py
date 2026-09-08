"""
Verificação estática do server.py - as mesmas garantias de segurança
já checadas assim no queue-api (test_server_routes.py): a proteção
precisa estar no lugar certo do código, não só existir em algum lugar.
"""
import re
from pathlib import Path

SERVER_PY = Path(__file__).parent.parent / "server.py"

FUNCTION_DEF_RE = re.compile(r"\n    def \w+\(")


def load_source():
    return SERVER_PY.read_text(encoding="utf-8")


def get_function_body(source: str, fn_name: str) -> str:
    """
    Retorna o corpo de um método (sem a linha 'def nome(...):'), até o
    próximo método da classe ou o fim do arquivo.
    """
    fn_start = source.index(f"def {fn_name}(")
    signature_end = source.index("):", fn_start) + 2
    match = FUNCTION_DEF_RE.search(source, signature_end)
    fn_end = match.start() if match else len(source)
    return source[signature_end:fn_end]


def test_login_disabled_by_default_without_bootstrap_or_users():
    source = load_source()
    bootstrap_body = get_function_body(source, "ensure_bootstrap_admin")
    assert "if not ADMIN_PASSWORD_HASH:" in bootstrap_body

    login_body = get_function_body(source, "_handle_login")
    assert "if not users:" in login_body


def test_role_checks_happen_before_any_mutation():
    """
    Toda rota que muda ramal/usuário/lista de bloqueio/modo feriado
    precisa checar o papel ANTES de mexer no store/AMI - senão a
    proteção é decorativa. Cada entrada é (função, papéis esperados,
    chamada de mutação que ela dispara).
    """
    source = load_source()

    checks = [
        ("_handle_create_extension", {"admin"}, "add_extension("),
        ("_handle_update_extension", {"admin"}, "update_extension("),
        ("_handle_delete_extension", {"admin"}, "delete_extension("),
        ("_handle_add_to_blocklist", {"admin"}, "block_number("),
        ("_handle_remove_from_blocklist", {"admin"}, "unblock_number("),
        ("_handle_add_vip", {"admin"}, "set_vip("),
        ("_handle_remove_vip", {"admin"}, "remove_vip("),
        ("_handle_set_holiday_mode", {"admin", "supervisor"}, "set_holiday_mode("),
        ("_handle_create_user", {"admin"}, "add_user("),
        ("_handle_update_user", {"admin"}, "update_user("),
        ("_handle_delete_user", {"admin"}, "delete_user("),
    ]

    for fn_name, expected_roles, mutation_call in checks:
        body = get_function_body(source, fn_name)

        assert "_require_role(" in body, f"{fn_name} não usa _require_role - checagem ausente"
        role_call_pos = body.index("_require_role(")
        role_set_text = body[role_call_pos:body.index(")", role_call_pos) + 1]
        for role in expected_roles:
            assert f'"{role}"' in role_set_text, f"{fn_name} deveria permitir o papel '{role}'"

        assert mutation_call in body, f"{fn_name} não parece chamar {mutation_call} - verifique o teste"
        mutation_pos = body.index(mutation_call)
        assert role_call_pos < mutation_pos, (
            f"{fn_name} muta o store/AMI antes de checar o papel"
        )


def test_get_routes_require_appropriate_role():
    source = load_source()
    do_get_body = get_function_body(source, "do_GET")

    for path_fragment, expected_roles in [
        ("/api/extensions", {"admin", "supervisor"}),
        ("/api/blocklist", {"admin", "supervisor"}),
        ("/api/vip", {"admin", "supervisor"}),
        ("/api/config/modo-feriado", {"admin", "supervisor"}),
        ("/api/users", {"admin"}),
    ]:
        branch_start = do_get_body.index(path_fragment)
        branch_text = do_get_body[branch_start:branch_start + 200]
        assert "_require_role(" in branch_text, f"GET {path_fragment} sem checagem de papel"
        role_call_pos = branch_text.index("_require_role(")
        role_set_text = branch_text[role_call_pos:branch_text.index(")", role_call_pos) + 1]
        for role in expected_roles:
            assert f'"{role}"' in role_set_text, (
                f"GET {path_fragment} deveria permitir o papel '{role}'"
            )


def test_password_is_stripped_before_sending_to_browser():
    source = load_source()
    assert "def public_view(extension: dict)" in source
    assert '!= "password"' in source
    assert "public_view(" in source


def test_password_hash_is_stripped_before_sending_users_to_browser():
    source = load_source()
    assert "public_user(" in source


def test_only_one_role_can_toggle_holiday_mode_and_it_includes_supervisor():
    """
    Modo feriado é operacional (não destrutivo) - por isso supervisor
    também pode alternar, diferente de ramal/bloqueio/usuários que são
    admin-only. Esse teste garante que a distinção não se perde numa
    refatoração futura.
    """
    source = load_source()
    holiday_body = get_function_body(source, "_handle_set_holiday_mode")
    extension_body = get_function_body(source, "_handle_create_extension")

    assert '"supervisor"' in holiday_body
    assert '"supervisor"' not in extension_body


def test_totp_setup_and_confirm_only_require_own_authentication():
    """
    2FA é autoatendimento - configurar o 2FA da PRÓPRIA conta só
    precisa estar logado, não precisa ser admin (senão supervisor
    nunca conseguiria proteger a própria conta).
    """
    source = load_source()
    for fn_name in ("_handle_totp_setup", "_handle_totp_confirm"):
        body = get_function_body(source, fn_name)
        assert "_require_auth()" in body
        assert "_require_role(" not in body


def test_totp_confirm_does_not_enable_before_verifying_code():
    """
    O segredo é salvo com totp_enabled=False no setup, e só vira True
    depois que um código válido é conferido - nunca antes.
    """
    source = load_source()
    body = get_function_body(source, "_handle_totp_confirm")
    verify_pos = body.index("verify_totp(")
    enable_pos = body.index('"totp_enabled": True')
    assert verify_pos < enable_pos


def test_totp_disable_requires_password_confirmation():
    source = load_source()
    body = get_function_body(source, "_handle_totp_disable")
    verify_pos = body.index("verify_password(")
    disable_pos = body.index('"totp_enabled": False')
    assert verify_pos < disable_pos


def test_login_returns_pending_token_instead_of_real_session_when_totp_enabled():
    """
    Se o usuário tem 2FA ligado, o login NUNCA deve devolver um token
    de sessão de verdade antes do código ser confirmado - senão o
    segundo fator é só decorativo.
    """
    source = load_source()
    body = get_function_body(source, "_handle_login")
    totp_check_pos = body.index('user.get("totp_enabled")')
    real_session_calls = [m.start() for m in re.finditer(r'sessions\.create\(username, role=user\["role"\]\)', body)]
    assert len(real_session_calls) == 1
    assert totp_check_pos < real_session_calls[0]


def test_verify_totp_login_checks_pending_role_sentinel():
    """
    O endpoint que completa o login com o código TOTP precisa exigir
    que o token pré-autenticação seja realmente do tipo "pendente de
    2FA" - senão uma sessão comum poderia ser reaproveitada aqui.
    """
    source = load_source()
    body = get_function_body(source, "_handle_verify_totp_login")
    assert "TOTP_PENDING_ROLE" in body


# ---------- Multi-tenant (backlog #38) ----------

def test_tenant_is_validated_before_any_astdb_mutation():
    """
    Backlog #38: bloqueio/VIP/feriado agora são famílias AstDB por
    tenant (blocklist-{tenant}, vip-{tenant}, config-{tenant}) - um
    tenant inválido/desconhecido não pode criar uma família nova
    silenciosamente, precisa ser rejeitado ANTES de qualquer chamada
    à AMI.
    """
    source = load_source()

    checks = [
        ("_handle_add_to_blocklist", "block_number("),
        ("_handle_remove_from_blocklist", "unblock_number("),
        ("_handle_add_vip", "set_vip("),
        ("_handle_remove_vip", "remove_vip("),
        ("_handle_set_holiday_mode", "set_holiday_mode("),
    ]

    for fn_name, mutation_call in checks:
        body = get_function_body(source, fn_name)
        assert "validate_tenant(" in body, f"{fn_name} não valida o tenant"
        tenant_check_pos = body.index("validate_tenant(")
        mutation_pos = body.index(mutation_call)
        assert tenant_check_pos < mutation_pos, (
            f"{fn_name} muta o AstDB antes de validar o tenant"
        )


def test_unknown_tenant_is_rejected_not_silently_defaulted():
    """
    validate_tenant() precisa recusar um tenant fora da lista de
    conhecidos (estáticos t1/t2 + criados pelo wizard, backlog #39) -
    se aceitasse qualquer string, alguém poderia criar famílias AstDB
    arbitrárias (blocklist-t99, por exemplo) que o dialplan nunca
    consultaria, dando falsa sensação de que o bloqueio funcionou.
    """
    source = load_source()
    fn_body = get_function_body(source, "validate_tenant")
    assert "STATIC_TENANTS" in fn_body
    assert "load_tenants(TENANTS_PATH)" in fn_body


def test_extension_listing_filters_by_tenant_query_param():
    """
    Sem esse filtro, o painel sempre mostraria ramais de TODOS os
    tenants juntos, independente do tenant selecionado na interface.
    """
    source = load_source()
    do_get_body = get_function_body(source, "do_GET")
    extensions_branch_start = do_get_body.index('"/api/extensions"')
    extensions_branch = do_get_body[extensions_branch_start:extensions_branch_start + 400]
    assert "tenant_filter" in extensions_branch
    assert 'e.get("tenant"' in extensions_branch


def test_create_tenant_requires_admin_role():
    source = load_source()
    body = get_function_body(source, "_handle_create_tenant")
    assert '_require_role({"admin"})' in body


def test_create_tenant_validates_before_writing_any_file():
    """
    A validação (tenant novo, DID não duplicado, etc.) precisa
    acontecer ANTES de escrever qualquer arquivo de config - senão um
    tenant inválido deixaria arquivos órfãos no disco.
    """
    source = load_source()
    body = get_function_body(source, "_handle_create_tenant")
    validate_pos = body.index("validate_tenant_creation_input(")
    write_pos = body.index("write_text(")
    assert validate_pos < write_pos


def test_create_tenant_registers_did_and_persists_only_after_success():
    source = load_source()
    body = get_function_body(source, "_handle_create_tenant")
    assert "register_tenant_did(" in body
    assert "save_tenants(" in body


def test_monitoring_pin_endpoints_require_admin_not_supervisor():
    """
    Mais restrito que modo feriado de propósito - configurar
    monitoramento habilita vigilância de conversa de terceiros, uma
    ação de peso diferente de ligar uma mensagem de feriado.
    """
    source = load_source()
    for fn_name in ("_handle_set_monitoring_pin", "_handle_disable_monitoring"):
        body = get_function_body(source, fn_name)
        assert '_require_role({"admin"})' in body
        assert "supervisor" not in body


def test_monitoring_pin_validated_before_writing_to_astdb():
    source = load_source()
    body = get_function_body(source, "_handle_set_monitoring_pin")
    validate_pos = body.index("validate_monitoring_pin_input(")
    write_pos = body.index("set_monitoring_pin(")
    assert validate_pos < write_pos


def test_monitoring_pin_value_never_returned_to_browser():
    """
    O endpoint de consulta só informa SE está configurado
    (True/False), nunca o PIN em si - mesmo princípio de nunca
    devolver hash de senha.
    """
    source = load_source()
    assert "is_monitoring_configured(" in source
    assert '"configured":' in source


def test_generate_sound_requires_admin_role():
    """
    Gerar áudio pro dialplan (backlog #48) é uma ação de conteúdo
    público (todo cliente que ligar vai ouvir) - mais parecido com
    criar ramal do que com uma leitura qualquer, admin-only.
    """
    source = load_source()
    body = get_function_body(source, "_handle_generate_sound")
    assert '_require_role({"admin"})' in body
