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
