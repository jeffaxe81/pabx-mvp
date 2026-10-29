from tenants import (
    validate_tenant_creation_input, load_tenants, save_tenants,
    render_tenant_pjsip, render_tenant_queues, render_tenant_extensions, render_tenant_voicemail,
    render_tenant_parking, validate_tenant_removal, generate_tenant_credentials, generate_tenant_voicemail_pins,
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


def test_render_pjsip_uses_different_strong_passwords():
    content = render_tenant_pjsip("t3")
    passwords = [line.split("=", 1)[1] for line in content.splitlines()
                 if line.startswith("password=")]
    assert len(passwords) == 2
    assert all(len(p) >= 32 for p in passwords)
    assert passwords[0] != passwords[1]
    assert "troque_esta_senha" not in content


def test_new_tenant_credentials_are_unpredictable():
    first = generate_tenant_credentials("t3")
    second = generate_tenant_credentials("t3")
    assert first.keys() == {"t3-recepcao", "t3-recepcao-2"}
    assert all(len(secret) >= 32 for secret in first.values())
    assert len(set(first.values()) | set(second.values())) == 4


def test_render_tenant_pjsip_receives_same_credentials_returned_to_admin():
    creds = {"t3-recepcao": "A" * 32, "t3-recepcao-2": "B" * 32}
    generated = render_tenant_pjsip("t3", creds)
    assert "password=" + creds["t3-recepcao"] in generated
    assert "password=" + creds["t3-recepcao-2"] in generated


def test_render_tenant_pjsip_fails_closed_on_weak_or_missing_credentials():
    import pytest
    for credentials in ({}, {"t3-recepcao": "123", "t3-recepcao-2": "B" * 32},
                        {"t3-recepcao": "A" * 32, "t3-recepcao-2": "bad\nINJECT"}):
        with pytest.raises(ValueError):
            render_tenant_pjsip("t3", credentials)


def test_credential_generation_rejects_unsafe_tenant_id():
    import pytest
    with pytest.raises(ValueError):
        generate_tenant_credentials("t3\nsecret=abc")


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
    assert "Queue(${FILA_IDIOMA},c,,,${OVERFLOW_TIMEOUT})" in content
    assert 'QUEUESTATUS}" = "CONTINUE"' in content


def test_render_extensions_supports_queue_overflow():
    """Backlog #45: tenant novo já nasce com a mesma lógica de overflow entre filas de t1/t2."""
    content = render_tenant_extensions("t3")
    assert 'GotoIf($["${QUEUESTATUS}" = "TIMEOUT"]?fila-overflow,1)' in content
    assert "exten => fila-overflow,1," in content
    assert "exten => fazer-overflow,1," in content
    assert "Goto(1000,1)" in content


def test_render_extensions_overflow_timeout_configurable_per_tenant():
    """Backlog #56: tenant novo já nasce com a mesma flexibilidade de ajustar o timeout de overflow pelo painel."""
    content = render_tenant_extensions("t3")
    assert "DB(config-${TENANT}/overflow-timeout-segundos)" in content


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


def test_render_extensions_includes_conference_room_pattern():
    """Backlog #43: tenant novo já nasce com sala de conferência ad-hoc própria."""
    content = render_tenant_extensions("t3")
    assert "exten => _40XXXX,1,Set(TENANT=t3)" in content
    assert "ConfBridge(sala-${TENANT}-${EXTEN:2}" in content


def test_render_extensions_includes_dynamic_ramal_files():
    content = render_tenant_extensions("t3")
    assert "#include generated/extensions_dynamic_dial-t3.conf" in content
    assert "#include generated/extensions_dynamic_hints-t3.conf" in content


# ---------- render_tenant_voicemail ----------

def test_render_voicemail_creates_telephonist_mailboxes():
    content = render_tenant_voicemail("t3")
    assert "[t3]" in content
    assert "t3-1001 => " in content
    assert "t3-recepcao => " in content
    assert "t3-recepcao-2 => " in content
    assert "=> 1234," not in content
    assert "#include generated/voicemail_dynamic_t3.conf" in content


def test_voicemail_pins_are_random_unique_and_eight_digits():
    first = generate_tenant_voicemail_pins("t3")
    second = generate_tenant_voicemail_pins("t3")
    assert set(first) == {"t3-1001", "t3-recepcao", "t3-recepcao-2"}
    assert all(pin.isdigit() and len(pin) == 8 for pin in first.values())
    assert len(set(first.values())) == 3
    assert first != second


def test_voicemail_render_uses_pins_generated_for_response():
    pins = {"t3-1001": "24681357", "t3-recepcao": "12345678",
            "t3-recepcao-2": "87654321"}
    content = render_tenant_voicemail("t3", pins)
    assert "t3-1001 => 24681357," in content
    assert "t3-recepcao => 12345678," in content
    assert "t3-recepcao-2 => 87654321," in content


def test_voicemail_render_rejects_weak_or_reused_pins():
    import pytest
    for pins in (
        {"t3-1001": "24681357", "t3-recepcao": "1234", "t3-recepcao-2": "87654321"},
        {"t3-1001": "24681357", "t3-recepcao": "24681357", "t3-recepcao-2": "87654321"},
        {"t3-1001": "24681357", "t3-recepcao": "12345678", "t3-recepcao-2": "12345678"},
        {"t3-1001": "24681357", "t3-recepcao": "12345678", "t3-recepcao-2": "5678901\\nsecret"},
        {"t3-recepcao": "12345678", "t3-recepcao-2": "87654321"},
        {},
    ):
        with pytest.raises(ValueError):
            render_tenant_voicemail("t3", pins)


# ---------- render_tenant_parking ----------

def test_render_parking_creates_lot_scoped_to_tenant_context():
    content = render_tenant_parking("t3")
    assert "[parkinglot-t3]" in content
    assert "context = t3-internal" in content
    assert "parkext = 75" in content
    assert "parkpos = 76-95" in content


def test_render_parking_rings_back_to_origin_when_unretrieved():
    content = render_tenant_parking("t3")
    assert "comebacktoorigin = yes" in content


# ---------- validate_tenant_removal (backlog #52) ----------

def test_removal_rejects_t1_and_t2():
    """t1/t2 são exemplos estáticos do projeto, nunca gerenciados pelo wizard."""
    for reserved in ("t1", "t2"):
        ok, error, _ = validate_tenant_removal(reserved, existing=[])
        assert ok is False
        assert "estáticos" in error


def test_removal_rejects_unknown_tenant():
    ok, error, _ = validate_tenant_removal("t7", existing=[{"tenant_id": "t3", "did": "1", "display_name": "x"}])
    assert ok is False
    assert "não encontrado" in error


def test_removal_accepts_existing_tenant_and_returns_record():
    existing = [{"tenant_id": "t3", "did": "5511900003333", "display_name": "Empresa C"}]
    ok, error, record = validate_tenant_removal("t3", existing)
    assert ok is True
    assert record == existing[0]


def test_removal_is_case_and_whitespace_tolerant():
    existing = [{"tenant_id": "t3", "did": "1", "display_name": "x"}]
    ok, error, record = validate_tenant_removal("  T3  ", existing)
    assert ok is True
    assert record["tenant_id"] == "t3"

# ---------- segurança de entrada no wizard ----------

def test_creation_rejects_payloads_that_are_not_json_objects():
    for payload in (None, [], "t3", 99, True):
        ok, error, cleaned = validate_tenant_creation_input(payload, [])
        assert ok is False
        assert cleaned is None
        assert error


def test_creation_rejects_wrong_field_types_without_exception():
    for field, value in (
        ("tenant_id", 3),
        ("tenant_id", ["t3"]),
        ("did", 5511900003333),
        ("did", {"number": "5511900003333"}),
        ("display_name", ["Empresa"]),
        ("display_name", None),
    ):
        data = {**VALID_INPUT, field: value}
        ok, error, cleaned = validate_tenant_creation_input(data, [])
        assert ok is False
        assert cleaned is None
        assert error


def test_creation_rejects_letters_and_control_characters_in_did():
    for bad in ("abc5511900003333", "5511900003333xyz",
                "5511900003333\nAction: Command", "5511900003333;rm -rf /"):
        ok, _, cleaned = validate_tenant_creation_input(
            {**VALID_INPUT, "did": bad}, []
        )
        assert ok is False and cleaned is None


def test_creation_rejects_control_characters_in_display_name():
    ok, error, cleaned = validate_tenant_creation_input(
        {**VALID_INPUT, "display_name": "Empresa C\r\nsecret=abc"}, []
    )
    assert ok is False and cleaned is None
    assert "nome" in error


def test_creation_fails_closed_on_corrupted_existing_tenant_records():
    for existing in (None, {}, "not-json", [None], [{}], [{"tenant_id": "t4"}]):
        ok, error, cleaned = validate_tenant_creation_input(VALID_INPUT, existing)
        assert ok is False and cleaned is None
        assert "cadastro" in error


def test_removal_rejects_nonstring_and_invalid_tenant_id():
    records = [{"tenant_id": "t3", "did": "5511900003333", "display_name": "Empresa C"}]
    for bad in (None, [], 3, "../t3", "t3/../../manager.conf", "t3\n"):
        # Espaço é tolerado, mas quebras de linha ou caminho não são.
        ok, _, cleaned = validate_tenant_removal(bad, records)
        assert ok is False and cleaned is None


def test_removal_fails_closed_on_invalid_registry():
    for existing in (None, {}, [{}], [{"tenant_id": "t3"}]):
        ok, error, cleaned = validate_tenant_removal("t3", existing)
        assert ok is False and cleaned is None
        assert error

def test_parser_finds_only_explicit_inbound_dids_in_gateway_context():
    from tenants import parse_static_inbound_dids
    config = """
[t1-internal]
exten => 5511900009999,1,Dial(PJSIP/t1)
[from-tdm-gateway]
; exten => 5511900007777,1,NoOp(comentado)
exten => 5511900001111,1,Set(TENANT=t1)
 same => n,Goto(t1-internal,1001,1)
exten => 5511900002222,1,Set(TENANT=t2)
exten => _X.,1,Set(TENANT=${DB(tenant-did/${EXTEN})})
[ura-principal]
exten => 5511900008888,1,Answer()
"""
    assert parse_static_inbound_dids(config) == {
        "5511900001111", "5511900002222"
    }


def test_parser_fails_closed_without_inbound_context():
    import pytest
    from tenants import parse_static_inbound_dids
    with pytest.raises(ValueError, match="from-tdm-gateway"):
        parse_static_inbound_dids("[t1-internal]\nexten => 123456789,1,Answer()")


def test_create_tenant_rejects_did_that_has_static_dialplan_route():
    record = {**VALID_INPUT, "did": "5511900001111"}
    ok, error, cleaned = validate_tenant_creation_input(
        record, existing=[], reserved_dids={"5511900001111", "5511900002222"}
    )
    assert not ok and cleaned is None
    assert "rota estática" in error


def test_create_tenant_allows_new_did_not_in_static_dialplan():
    ok, error, cleaned = validate_tenant_creation_input(
        VALID_INPUT, existing=[], reserved_dids={"5511900001111"}
    )
    assert ok and error is None
    assert cleaned["did"] == VALID_INPUT["did"]


def test_parser_reads_repository_real_inbound_context():
    from pathlib import Path
    from tenants import parse_static_inbound_dids
    dialplan = (Path(__file__).resolve().parents[2] / "asterisk" / "extensions.conf").read_text(encoding="utf-8")
    reserved = parse_static_inbound_dids(dialplan)
    assert "5511900001111" in reserved
    assert "5511900002222" in reserved

def test_dynamic_tenant_voicemail_fallback_exists_in_same_tenant():
    """VoiceMail(tN-1001@tN) in Queue/URA must resolve to a real mailbox."""
    for tenant in ("t3", "t10"):
        dialplan = render_tenant_extensions(tenant)
        voicemail = render_tenant_voicemail(tenant)
        assert f"VoiceMail(${{TENANT}}-1001@${{TENANT}},u)" in dialplan
        assert f"[{tenant}]" in voicemail
        assert f"{tenant}-1001 => " in voicemail
        assert f"t1-1001 => " not in voicemail

