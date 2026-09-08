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
    "tenantWizardCard", "tenantsTableBody", "tenantsEmptyHint",
    "wizardTenantIdInput", "wizardDidInput", "wizardDisplayNameInput", "wizardReviewBtn",
    "wizardReviewList", "wizardConfirmBtn", "wizardBackBtn", "tenantWizardResult", "tenantWizardError",
    "monitoringPinCard", "monitoringStatusText", "monitoringPinInput", "setMonitoringPinBtn", "disableMonitoringBtn", "monitoringPinError",
    "ttsCard", "ttsFilenameInput", "ttsLanguageSelect", "ttsEngineSelect", "ttsTextInput", "generateTtsBtn", "ttsResult", "ttsError",
    "soundsTableBody", "soundsEmptyHint",
    "soundPlayer",
    "overflowTimeoutInput", "setOverflowTimeoutBtn", "overflowTimeoutError",
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


# ---------- Wizard de preparação de ambiente (backlog #39) ----------

def test_tenant_wizard_hidden_from_supervisor():
    html = load_html()
    fn_start = html.index("function applyRolePermissions")
    fn_end = html.index("}", html.index("continua visível", fn_start))
    body = html[fn_start:fn_end]
    assert "tenantWizardCard" in body


def test_wizard_has_two_step_flow_with_review_before_creating():
    """
    Criar um tenant gera arquivos de config de verdade e recarrega o
    Asterisk - não pode ser um clique só sem confirmação, tem que
    passar por uma etapa de revisão antes.
    """
    html = load_html()
    assert 'id="tenantWizardStep1"' in html
    assert 'id="tenantWizardStep2"' in html
    review_start = html.index("el('wizardReviewBtn').addEventListener")
    review_end = html.index("});", review_start)
    review_body = html[review_start:review_end]
    assert "tenantWizardStep1').style.display = 'none'" in review_body
    assert "tenantWizardStep2').style.display = 'block'" in review_body


def test_wizard_confirm_posts_to_tenants_endpoint():
    html = load_html()
    confirm_start = html.index("el('wizardConfirmBtn').addEventListener")
    confirm_end = html.index("});", html.index("catch", confirm_start))
    body = html[confirm_start:confirm_end]
    assert "/api/tenants" in body
    assert "method: 'POST'" in body


def test_wizard_reports_reload_failure_without_hiding_it():
    """
    Se o reload automático falhar (Asterisk fora do ar no momento),
    a interface precisa avisar isso claramente em vez de fingir
    sucesso completo - o tenant foi criado, mas precisa de atenção.
    """
    html = load_html()
    confirm_start = html.index("el('wizardConfirmBtn').addEventListener")
    confirm_end = html.index("});", html.index("catch", confirm_start))
    body = html[confirm_start:confirm_end]
    assert "reload_error" in body


# ---------- PIN de monitoramento de chamada (backlog #42) ----------

def test_monitoring_pin_card_hidden_from_supervisor():
    html = load_html()
    fn_start = html.index("function applyRolePermissions")
    fn_end = html.index("}", html.index("continua visível", fn_start))
    body = html[fn_start:fn_end]
    assert "monitoringPinCard" in body


def test_monitoring_pin_section_warns_about_legal_implications():
    """
    Monitoramento de chamada é vigilância de conversa de terceiros -
    a interface precisa deixar isso claro antes de alguém configurar,
    não só oferecer o botão sem contexto nenhum.
    """
    html = load_html()
    section_start = html.index('id="monitoringPinCard"')
    section_end = html.index('id="monitoringPinError"', section_start)
    section_html = html[section_start:section_end]
    assert "legais" in section_html.lower() or "jurídic" in section_html.lower()


def test_disable_monitoring_requires_confirmation():
    html = load_html()
    fn_start = html.index("el('disableMonitoringBtn').addEventListener")
    fn_end = html.index("});", fn_start)
    body = html[fn_start:fn_end]
    assert "confirm(" in body


def test_monitoring_requests_include_current_tenant():
    html = load_html()
    assert "/api/monitoring-pin?tenant=${currentTenant}" in html
    assert "tenant: currentTenant" in html


# ---------- Gerar áudio por texto / TTS (backlog #48) ----------

def test_tts_card_hidden_from_supervisor():
    html = load_html()
    fn_start = html.index("function applyRolePermissions")
    fn_end = html.index("}", html.index("continua visível", fn_start))
    body = html[fn_start:fn_end]
    assert "ttsCard" in body


def test_tts_section_warns_about_xtts_licensing():
    """
    XTTS-v2 tem licença não-comercial - a interface precisa deixar
    isso claro, não só oferecer o motor como uma opção qualquer.
    """
    html = load_html()
    section_start = html.index('id="ttsCard"')
    section_end = html.index('id="ttsError"', section_start)
    section_html = html[section_start:section_end]
    assert "não-comercial" in section_html.lower() or "nao-comercial" in section_html.lower()


def test_selecting_xtts_requires_extra_confirmation():
    """
    Escolher XTTS não pode ser um clique só - precisa de uma
    confirmação extra, já que é uma decisão com risco de
    licenciamento se usada comercialmente por engano.
    """
    html = load_html()
    fn_start = html.index("el('generateTtsBtn').addEventListener")
    fn_end = html.index("});", html.index("catch", fn_start))
    body = html[fn_start:fn_end]
    assert "xtts" in body
    assert "confirm(" in body


def test_tts_generate_posts_to_sounds_endpoint():
    html = load_html()
    fn_start = html.index("el('generateTtsBtn').addEventListener")
    fn_end = html.index("});", html.index("catch", fn_start))
    body = html[fn_start:fn_end]
    assert "/api/sounds/generate" in body
    assert "method: 'POST'" in body


# ---------- Remoção de tenant pelo wizard (backlog #52) ----------

def test_remove_tenant_button_present_in_table():
    html = load_html()
    fn_start = html.index("function renderTenantsTable")
    fn_end = html.index("}\n\n", fn_start)
    body = html[fn_start:fn_end]
    assert "data-remove-tenant" in body


def test_remove_tenant_requires_confirmation():
    html = load_html()
    fn_start = html.index("function removeTenant")
    fn_end = html.index("}\n\n", fn_start)
    body = html[fn_start:fn_end]
    assert "confirm(" in body


def test_remove_tenant_calls_delete_endpoint():
    html = load_html()
    fn_start = html.index("function removeTenant")
    fn_end = html.index("}\n\n", fn_start)
    body = html[fn_start:fn_end]
    assert "/api/tenants/${tenantId}" in body
    assert "method: 'DELETE'" in body


def test_remove_tenant_reports_orphaned_extensions_cleaned_up():
    """Backlog #54: o admin precisa saber quantos ramais dinâmicos também foram removidos, não só o tenant em si."""
    html = load_html()
    fn_start = html.index("function removeTenant")
    fn_end = html.index("}\n\n", fn_start)
    body = html[fn_start:fn_end]
    assert "removed_extensions" in body


# ---------- Lista de áudios existentes (backlog #53) ----------

def test_sounds_loaded_on_login():
    html = load_html()
    fn_start = html.index("function handlePostLogin") if "function handlePostLogin" in html else html.index("loadTotpStatus();")
    body = html[fn_start:fn_start + 400]
    assert "loadSounds();" in body


def test_sounds_reload_after_generating_new_audio():
    html = load_html()
    fn_start = html.index("el('generateTtsBtn').addEventListener")
    fn_end = html.index("});", html.index("catch", fn_start))
    body = html[fn_start:fn_end]
    assert "loadSounds();" in body


def test_sounds_table_shows_filename_size_and_date():
    html = load_html()
    fn_start = html.index("function renderSoundsTable")
    fn_end = html.index("}\n})", fn_start) if "}\n})" in html[fn_start:] else html.index("}\n\n", fn_start)
    body = html[fn_start:fn_end]
    assert "s.filename" in body
    assert "size_bytes" in body
    assert "modified_at" in body


# ---------- Overflow entre filas (backlog #56) ----------

def test_overflow_timeout_loaded_on_login_and_tenant_change():
    html = load_html()
    assert html.count("loadOverflowTimeout();") == 2  # login + troca de tenant


def test_overflow_timeout_requests_include_current_tenant():
    html = load_html()
    assert "/api/config/overflow-timeout?tenant=${currentTenant}" in html
    fn_start = html.index("el('setOverflowTimeoutBtn').addEventListener")
    fn_end = html.index("});", html.index("catch", fn_start))
    body = html[fn_start:fn_end]
    assert "tenant: currentTenant" in body


def test_overflow_timeout_save_sends_number_not_string():
    """O input HTML devolve string por padrão - precisa converter pra número antes de enviar."""
    html = load_html()
    fn_start = html.index("el('setOverflowTimeoutBtn').addEventListener")
    fn_end = html.index("});", html.index("catch", fn_start))
    body = html[fn_start:fn_end]
    assert "Number(el('overflowTimeoutInput').value)" in body


# ---------- Reprodução de áudio (backlog #60) ----------

def test_play_button_present_for_each_sound():
    html = load_html()
    fn_start = html.index("function renderSoundsTable")
    body = html[fn_start:fn_start + 700]
    assert "data-play-sound" in body


def test_play_sound_does_not_use_audio_src_attribute_directly():
    """
    Um <audio src="..."> não manda o header Authorization - a busca
    precisa ser via fetch() manual com o token, não a tag HTML direto.
    """
    html = load_html()
    fn_start = html.index("function playSound")
    fn_end = html.index("}\n\n", fn_start) if "}\n\n" in html[fn_start:] else html.index("}\n  }", fn_start)
    body = html[fn_start:fn_end]
    assert "Authorization: `Bearer ${token}`" in body
    assert "res.blob()" in body


def test_play_sound_creates_object_url_for_playback():
    html = load_html()
    fn_start = html.index("function playSound")
    fn_end = html.index("}\n\n", fn_start) if "}\n\n" in html[fn_start:] else html.index("}\n  }", fn_start)
    body = html[fn_start:fn_end]
    assert "URL.createObjectURL(blob)" in body
    assert "player.play()" in body


def test_play_sound_revokes_previous_object_url():
    """
    Backlog #61: sem isso, cada clique em "Reproduzir" acumula
    memória não liberada no navegador (URLs de objeto nunca revogadas
    entre uma reprodução e outra).
    """
    html = load_html()
    fn_start = html.index("function playSound")
    fn_end = html.index("}\n\n", fn_start) if "}\n\n" in html[fn_start:] else html.index("}\n  }", fn_start)
    body = html[fn_start:fn_end]
    revoke_pos = body.index("URL.revokeObjectURL(")
    create_pos = body.index("URL.createObjectURL(")
    assert revoke_pos < create_pos
