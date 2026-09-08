from tts_service import validate_tts_request, ENGINE_PIPER, ENGINE_XTTS


def test_accepts_valid_request_with_default_engine():
    ok, error, cleaned = validate_tts_request({"text": "Bem-vindo à empresa"}, xtts_enabled=False)
    assert ok is True
    assert cleaned["engine"] == ENGINE_PIPER
    assert cleaned["language"] == "pt"


def test_rejects_empty_text():
    ok, error, _ = validate_tts_request({"text": ""}, xtts_enabled=False)
    assert ok is False
    assert "texto" in error


def test_rejects_missing_text():
    ok, error, _ = validate_tts_request({}, xtts_enabled=False)
    assert ok is False


def test_rejects_text_too_long():
    ok, error, _ = validate_tts_request({"text": "x" * 1001}, xtts_enabled=False)
    assert ok is False
    assert "longo" in error


def test_rejects_unsupported_language():
    ok, error, _ = validate_tts_request({"text": "hi", "language": "fr"}, xtts_enabled=False)
    assert ok is False


def test_accepts_all_supported_languages():
    for lang in ("pt", "en", "es"):
        ok, error, cleaned = validate_tts_request({"text": "hi", "language": lang}, xtts_enabled=False)
        assert ok is True
        assert cleaned["language"] == lang


def test_rejects_unknown_engine():
    ok, error, _ = validate_tts_request({"text": "hi", "engine": "google-tts"}, xtts_enabled=False)
    assert ok is False


# ---------- XTTS - a parte que importa de verdade ----------

def test_rejects_xtts_when_disabled():
    """
    Backlog #48: XTTS-v2 tem licença que proíbe uso comercial sem
    licença paga da Coqui (empresa que não existe mais) - por isso
    fica desligado por padrão, e o pedido precisa ser recusado
    explicitamente, não silenciosamente redirecionado pro Piper.
    """
    ok, error, _ = validate_tts_request({"text": "hi", "engine": ENGINE_XTTS}, xtts_enabled=False)
    assert ok is False
    assert "não-comercial" in error


def test_accepts_xtts_when_explicitly_enabled():
    ok, error, cleaned = validate_tts_request({"text": "hi", "engine": ENGINE_XTTS}, xtts_enabled=True)
    assert ok is True
    assert cleaned["engine"] == ENGINE_XTTS


def test_piper_never_blocked_by_xtts_flag():
    """Piper é o motor seguro comercialmente - nunca deveria depender da flag do XTTS."""
    ok, error, cleaned = validate_tts_request({"text": "hi", "engine": ENGINE_PIPER}, xtts_enabled=False)
    assert ok is True


# ---------- filename (backlog #48: regenerar um áudio específico da URA) ----------

def test_filename_defaults_to_none_when_not_provided():
    """None sinaliza pro server.py gerar um nome aleatório - não é toda geração que precisa de nome fixo."""
    ok, error, cleaned = validate_tts_request({"text": "hi"}, xtts_enabled=False)
    assert ok is True
    assert cleaned["filename"] is None


def test_explicit_filename_gets_wav_extension_appended():
    ok, error, cleaned = validate_tts_request({"text": "hi", "filename": "menu-principal-pt"}, xtts_enabled=False)
    assert ok is True
    assert cleaned["filename"] == "menu-principal-pt.wav"


def test_rejects_filename_with_invalid_characters():
    for bad_name in ("menu principal", "menu/principal", "MENU-PRINCIPAL", "a"):
        ok, error, _ = validate_tts_request({"text": "hi", "filename": bad_name}, xtts_enabled=False)
        assert ok is False, f"'{bad_name}' deveria ser rejeitado"
