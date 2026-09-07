"""
Testes de regressão do admin/index.html - mesmo padrão já usado pro
webphone/index.html (test_webphone_html.py).
"""
from pathlib import Path

ADMIN_HTML = Path(__file__).parent.parent / "admin" / "index.html"

REQUIRED_IDS = [
    "loginScreen", "loginUser", "loginPass", "loginBtn", "loginError",
    "totpScreen", "totpCodeInput", "totpVerifyBtn", "totpCancelBtn", "totpError",
    "appScreen", "logoutBtn",
    "extensionsTableBody", "emptyHint",
    "formTitle", "formName", "formNumber", "formDisplayName", "formPassword",
    "saveBtn", "cancelEditBtn", "formError",
    "blocklistTableBody", "blocklistEmptyHint", "blocklistInput", "addBlockBtn", "blocklistError",
    "vipFormCard", "vipTableBody", "vipEmptyHint", "vipNumberInput", "vipTargetInput", "addVipBtn", "vipError",
    "myRoleBadge", "usersFormCard", "usersTableBody",
    "userNameInput", "userRoleSelect", "userPasswordInput", "saveUserBtn",
    "cancelUserEditBtn", "userFormError",
    "totpSetupBtn", "totpSetupBlock", "totpSecretDisplay", "totpConfirmInput", "totpConfirmBtn",
    "totpDisableBlock", "totpDisablePasswordInput", "totpDisableBtn", "totpConfigError",
    "tenantSelect", "tenantLabel",
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


def test_blocklist_uses_bearer_token_like_extensions():
    html = load_html()
    assert "/api/blocklist" in html
    assert "loadBlocklist()" in html


def test_holiday_mode_toggle_present():
    html = load_html()
    assert 'id="holidayModeBtn"' in html
    assert "/api/config/modo-feriado" in html
    assert "loadHolidayMode()" in html


def test_vip_section_exists_and_manages_target_extension():
    html = load_html()
    assert "/api/vip" in html
    assert "loadVips()" in html
    assert "target_extension" in html


def test_users_section_exists_and_hidden_by_default():
    """
    A seção de usuários (backlog #19) só deve aparecer pra admin -
    começa escondida no HTML, e applyRolePermissions() decide se mostra.
    """
    html = load_html()
    assert 'id="usersFormCard" style="margin-top:24px; display:none;"' in html
    assert "/api/users" in html


def test_apply_role_permissions_hides_admin_only_cards_for_supervisor():
    html = load_html()
    fn_start = html.index("function applyRolePermissions")
    fn_end = html.index("}", html.index("continua visível", fn_start))
    body = html[fn_start:fn_end]
    assert "extensionFormCard" in body
    assert "blocklistFormCard" in body
    assert "usersFormCard" in body
    assert "isAdmin" in body


def test_login_stores_role_from_response():
    html = load_html()
    assert "myRole = data.role;" in html
    assert "applyRolePermissions()" in html


def test_login_handles_totp_required_flow():
    """
    O login precisa reconhecer requires_totp e mostrar a tela de
    verificação em vez de completar o login direto - senão o 2FA do
    backend fica sem efeito prático nenhum na interface.
    """
    html = load_html()
    fn_start = html.index("el('loginBtn').addEventListener")
    fn_end = html.index("});", html.index("catch", fn_start))
    body = html[fn_start:fn_end]
    assert "data.requires_totp" in body
    assert "pendingTotpToken = data.pending_token" in body
    assert "completeLogin(data)" in body


def test_totp_setup_flow_shows_secret_before_activation():
    html = load_html()
    setup_start = html.index("el('totpSetupBtn').addEventListener")
    setup_end = html.index("});", html.index("catch", setup_start))
    body = html[setup_start:setup_end]
    assert "/api/totp/setup" in body
    assert "totpSecretDisplay" in body


def test_totp_disable_sends_password_confirmation():
    html = load_html()
    disable_start = html.index("el('totpDisableBtn').addEventListener")
    disable_end = html.index("});", html.index("catch", disable_start))
    body = html[disable_start:disable_end]
    assert "/api/totp/disable" in body
    assert "totpDisablePasswordInput" in body


# ---------- Multi-tenant (backlog #38) ----------

def test_tenant_selector_offers_both_tenants():
    html = load_html()
    assert 'value="t1"' in html
    assert 'value="t2"' in html


def test_tenant_change_reloads_all_tenant_scoped_data():
    """
    Trocar de tenant precisa recarregar TUDO que é específico de
    tenant - ramais, bloqueio, VIP e feriado - senão a tela mostraria
    dados do tenant errado depois de trocar.
    """
    html = load_html()
    fn_start = html.index("el('tenantSelect').addEventListener")
    fn_end = html.index("});", fn_start)
    body = html[fn_start:fn_end]
    assert "currentTenant = e.target.value" in body
    assert "loadExtensions()" in body
    assert "loadBlocklist()" in body
    assert "loadVips()" in body
    assert "loadHolidayMode()" in body


def test_extensions_blocklist_vip_and_holiday_requests_include_tenant():
    """
    Backlog #38: toda consulta/mutação de dado por tenant precisa
    mandar o tenant certo - senão o painel sempre mostraria/mudaria o
    tenant 1 independente do que estivesse selecionado.
    """
    html = load_html()
    assert "/api/extensions?tenant=${currentTenant}" in html
    assert "/api/blocklist?tenant=${currentTenant}" in html
    assert "/api/vip?tenant=${currentTenant}" in html
    assert "/api/config/modo-feriado?tenant=${currentTenant}" in html
    assert "tenant: currentTenant" in html


def test_new_extension_form_tags_created_ramal_with_current_tenant():
    html = load_html()
    fn_start = html.index("el('saveBtn').addEventListener")
    fn_end = html.index("});", html.index("catch", fn_start))
    body = html[fn_start:fn_end]
    assert "tenant: currentTenant" in body
