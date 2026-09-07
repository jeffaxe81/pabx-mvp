from tenants import (
    validate_tenant_creation_input, load_tenants, save_tenants,
    render_tenant_pjsip, render_tenant_queues, render_tenant_extensions, render_tenant_voicemail,
)

VALID_INPUT = {"tenant_id": "t3", "did": "5511900003333", "display_name": "Empresa C"}


# ---------- validate_tenant_creation_input ----------

def test_accepts_correct_input():
    ok, error, cleaned = validate_tenant_creation_input(VALID_INPUT, existing=[])
    assert ok is True
    assert cleaned["tenant_id"] == "t3"
    assert cleaned["did"] == "5511900003333"


def test_rejects_t1_and_t2():
    """t1/t2 já são os exemplos estáticos originais - o wizard não pode sobrescrevê-los."""
    for reserved in ("t1", "t2"):
        ok, error, _ = validate_tenant_creation_input({**VALID_INPUT, "tenant_id": reserved}, existing=[])
        assert ok is False
        assert "t1/t2" in error


def test_rejects_malformed_tenant_id():
    for bad_id in ("tenant3", "t", "t0", "t3x"):
        ok, error, _ = validate_tenant_creation_input({**VALID_INPUT, "tenant_id": bad_id}, existing=[])
        assert ok is False, f"'{bad_id}' deveria ser rejeitado"


def test_tenant_id_is_normalized_to_lowercase():
    ok, error, cleaned = validate_tenant_creation_input({**VALID_INPUT, "tenant_id": "T3"}, existing=[])
    assert ok is True
    assert cleaned["tenant_id"] == "t3"


def test_rejects_duplicate_tenant_id():
    existing = [{"tenant_id": "t3", "did": "111", "display_name": "x"}]
    ok, error, _ = validate_tenant_creation_input(VALID_INPUT, existing)
    assert ok is False
    assert "já foi criado" in error


def test_rejects_duplicate_did():
    existing = [{"tenant_id": "t4", "did": "5511900003333", "display_name": "x"}]
    ok, error, _ = validate_tenant_creation_input(VALID_INPUT, existing)
    assert ok is False
    assert "já está registrado" in error


def test_sanitizes_did_formatting():
    ok, error, cleaned = validate_tenant_creation_input({**VALID_INPUT, "did": "+55 (11) 90000-3333"}, existing=[])
    assert ok is True
    assert cleaned["did"] == "5511900003333"


def test_rejects_missing_display_name():
    ok, error, _ = validate_tenant_creation_input({**VALID_INPUT, "display_name": ""}, existing=[])
    assert ok is False


# ---------- load/save ----------

def test_load_tenants_missing_file_returns_empty(tmp_path):
    assert load_tenants(tmp_path / "nao-existe.json") == []


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "tenants.json"
    save_tenants(path, [VALID_INPUT])
    assert load_tenants(path) == [VALID_INPUT]


# ---------- render_tenant_pjsip ----------

def test_render_pjsip_creates_two_telephonists():
    content = render_tenant_pjsip("t3")
    assert "[t3-recepcao](endpoint-webrtc)" in content
    assert "[t3-recepcao-2](endpoint-webrtc)" in content
    assert "context=t3-internal" in content
    assert "mailboxes=t3-recepcao@t3" in content


def test_render_pjsip_uses_different_passwords_for_each_telephonist():
    content = render_tenant_pjsip("t3")
    assert "password=troque_esta_senha_web_t3\n" in content
    assert "password=troque_esta_senha_web_t3_2\n" in content


# ---------- render_tenant_queues ----------

def test_render_queues_creates_three_language_queues():
    content = render_tenant_queues("t3")
    assert "[fila-t3]" in content
    assert "[fila-t3-en]" in content
    assert "[fila-t3-es]" in content
    assert "member => PJSIP/t3-recepcao" in content
    assert "member => PJSIP/t3-recepcao-2" in content


# ---------- render_tenant_extensions ----------

def test_render_extensions_creates_internal_and_hints_contexts():
    content = render_tenant_extensions("t3")
    assert "[t3-internal]" in content
    assert "[t3-hints]" in content


def test_render_extensions_mirrors_queue_entry_pattern():
    content = render_tenant_extensions("t3")
    assert "Queue(${FILA_IDIOMA},c)" in content
    assert 'QUEUESTATUS}" = "CONTINUE"' in content


def test_render_extensions_has_automatic_fallback_on_no_answer():
    content = render_tenant_extensions("t3")
    assert "Goto(t3-internal,1000,1)" in content
    assert 'DIALSTATUS}" = "ANSWER"' in content


def test_render_extensions_uses_tenant_specific_blocklist_family():
    content = render_tenant_extensions("t3")
    assert "DB(blocklist-t3/" in content


def test_render_extensions_plays_recording_consent_announcement():
    """
    Backlog #40 (conformidade LGPD): todo ponto que grava a chamada
    precisa avisar o cliente antes - senão o tenant novo já nasceria
    fora de conformidade, mesmo que t1/t2 estejam certos.
    """
    content = render_tenant_extensions("t3")
    assert content.count("Playback(custom/aviso-gravacao)") == 3  # 1000, 1010, 1011


def test_render_extensions_includes_dynamic_ramal_files():
    content = render_tenant_extensions("t3")
    assert "#include extensions_dynamic_dial-t3.conf" in content
    assert "#include extensions_dynamic_hints-t3.conf" in content


# ---------- render_tenant_voicemail ----------

def test_render_voicemail_creates_telephonist_mailboxes():
    content = render_tenant_voicemail("t3")
    assert "[t3]" in content
    assert "t3-recepcao => 1234" in content
    assert "t3-recepcao-2 => 1234" in content
    assert "#include voicemail_dynamic_t3.conf" in content
