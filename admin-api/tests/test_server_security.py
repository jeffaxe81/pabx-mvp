"""
Verificação estática do server.py - as mesmas garantias de segurança
já checadas assim no queue-api (test_server_routes.py): a proteção
precisa estar no lugar certo do código, não só existir em algum lugar.
"""
from pathlib import Path

SERVER_PY = Path(__file__).parent.parent / "server.py"


def load_source():
    return SERVER_PY.read_text(encoding="utf-8")


def test_login_disabled_by_default_without_password_hash():
    source = load_source()
    assert 'ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "")' in source
    fn_start = source.index("def _handle_login")
    fn_end = source.index("def _handle_logout")
    body = source[fn_start:fn_end]
    assert "if not ADMIN_PASSWORD_HASH:" in body


def test_all_extension_mutating_routes_require_auth_before_touching_store():
    """
    Criar/editar/apagar ramal, e adicionar/remover número da lista de
    bloqueio, precisam checar autenticação ANTES de mexer no store/AMI
    - senão a proteção é decorativa.
    """
    source = load_source()

    checks = [
        ("_handle_create_extension", "def do_PUT"),
        ("do_PUT", "def do_DELETE"),
        ("_handle_delete_extension", "def _handle_remove_from_blocklist"),
        ("_handle_remove_from_blocklist", "def main"),
        ("_handle_add_to_blocklist", "def _handle_login"),
    ]

    for fn_name, next_marker in checks:
        fn_start = source.index(f"def {fn_name}")
        fn_end = source.index(next_marker, fn_start)
        signature_end = source.index("):", fn_start) + 2
        body = source[signature_end:fn_end]  # exclui a linha "def nome(...):" da busca
        auth_pos = body.index("_require_auth()")
        mutation_candidates = [
            body.index(m) for m in (
                "add_extension(", "update_extension(", "delete_extension(",
                "block_number(", "unblock_number(",
            )
            if m in body
        ]
        assert mutation_candidates, f"{fn_name} não parece mutar nada - verifique o teste"
        assert auth_pos < min(mutation_candidates), (
            f"{fn_name} muta o store/AMI antes de checar autenticação"
        )


def test_password_is_stripped_before_sending_to_browser():
    source = load_source()
    assert "def public_view(extension: dict)" in source
    assert '!= "password"' in source
    assert "public_view(" in source


def test_get_blocklist_requires_auth():
    source = load_source()
    fn_start = source.index("def do_GET")
    fn_end = source.index("def _handle_list_blocklist")
    body = source[fn_start:fn_end]
    blocklist_branch = body[body.index("/api/blocklist"):]
    assert "_require_auth()" in blocklist_branch
