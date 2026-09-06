"""
Testes de regressão do admin/index.html - mesmo padrão já usado pro
webphone/index.html (test_webphone_html.py).
"""
from pathlib import Path

ADMIN_HTML = Path(__file__).parent.parent / "admin" / "index.html"

REQUIRED_IDS = [
    "loginScreen", "loginUser", "loginPass", "loginBtn", "loginError",
    "appScreen", "logoutBtn",
    "extensionsTableBody", "emptyHint",
    "formTitle", "formName", "formNumber", "formDisplayName", "formPassword",
    "saveBtn", "cancelEditBtn", "formError",
]


def load_html():
    return ADMIN_HTML.read_text(encoding="utf-8")


def test_all_required_ids_present():
    html = load_html()
    missing = [i for i in REQUIRED_IDS if f'id="{i}"' not in html]
    assert not missing, f"IDs esperados ausentes no HTML: {missing}"


def test_api_calls_send_bearer_token():
    """
    Sem o header Authorization, toda chamada autenticada da API
    falharia com 401 - checa que o helper central (apiFetch) sempre
    inclui o token quando disponível.
    """
    html = load_html()
    fn_start = html.index("function apiFetch")
    fn_end = html.index("});", fn_start)
    body = html[fn_start:fn_end]
    assert "Authorization" in body
    assert "Bearer" in body


def test_delete_requires_confirmation():
    html = load_html()
    fn_start = html.index("function deleteExtension")
    fn_end = html.index("}", html.index("catch", fn_start))
    body = html[fn_start:fn_end]
    assert "confirm(" in body


def test_password_field_is_optional_in_form():
    """
    O rótulo do campo precisa deixar claro que senha em branco gera
    uma automática - senão a telefonista tenta cadastrar sem senha e
    recebe um erro confuso.
    """
    html = load_html()
    assert "em branco" in html.lower() or "gera automático" in html.lower()
