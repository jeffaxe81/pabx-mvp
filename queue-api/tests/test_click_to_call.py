from click_to_call import (
    sanitize_phone_number,
    build_originate_action,
    validate_click_to_call_request,
)

VALID_CONFIG = {
    "api_key": "chave-secreta-123",
    "allowed_extensions": ["t1-recepcao"],
}


# ---------- sanitize_phone_number ----------

def test_sanitize_removes_formatting_characters():
    assert sanitize_phone_number("(11) 99999-8888") == "11999998888"


def test_sanitize_keeps_leading_plus():
    assert sanitize_phone_number("+55 11 99999-8888") == "+5511999998888"


def test_sanitize_rejects_too_short_numbers():
    assert sanitize_phone_number("1234") is None


def test_sanitize_rejects_empty_or_none():
    assert sanitize_phone_number("") is None
    assert sanitize_phone_number(None) is None


def test_sanitize_rejects_non_string_input():
    assert sanitize_phone_number(5511999998888) is None


def test_sanitize_strips_letters_and_symbols():
    assert sanitize_phone_number("liga pra 11999998888 por favor") == "11999998888"


# ---------- build_originate_action ----------

def test_build_originate_action_has_required_fields():
    action = build_originate_action("PJSIP/t1-recepcao", "11999998888", "click-to-call")
    assert action["Action"] == "Originate"
    assert action["Channel"] == "PJSIP/t1-recepcao"
    assert action["Context"] == "click-to-call"
    assert action["Exten"] == "11999998888"
    assert action["Async"] == "true"


def test_build_originate_action_uses_custom_caller_id():
    action = build_originate_action("PJSIP/t1-recepcao", "123", "ctx", caller_id_name="Loja Centro")
    assert "Loja Centro" in action["CallerID"]


# ---------- validate_click_to_call_request ----------

def test_validate_rejects_when_not_configured():
    ok, error, ext, number = validate_click_to_call_request(
        {"extension": "t1-recepcao", "number": "11999998888"}, "qualquer-chave", {"api_key": "", "allowed_extensions": []}
    )
    assert ok is False
    assert "não está configurado" in error


def test_validate_rejects_wrong_api_key():
    ok, error, ext, number = validate_click_to_call_request(
        {"extension": "t1-recepcao", "number": "11999998888"}, "chave-errada", VALID_CONFIG
    )
    assert ok is False
    assert "inválida" in error


def test_validate_rejects_missing_api_key():
    ok, error, ext, number = validate_click_to_call_request(
        {"extension": "t1-recepcao", "number": "11999998888"}, "", VALID_CONFIG
    )
    assert ok is False


def test_validate_rejects_extension_not_in_allowlist():
    ok, error, ext, number = validate_click_to_call_request(
        {"extension": "t1-1001", "number": "11999998888"}, VALID_CONFIG["api_key"], VALID_CONFIG
    )
    assert ok is False
    assert "não autorizado" in error


def test_validate_rejects_invalid_number():
    ok, error, ext, number = validate_click_to_call_request(
        {"extension": "t1-recepcao", "number": "123"}, VALID_CONFIG["api_key"], VALID_CONFIG
    )
    assert ok is False
    assert "número inválido" in error


def test_validate_accepts_correct_request():
    ok, error, ext, number = validate_click_to_call_request(
        {"extension": "t1-recepcao", "number": "(11) 99999-8888"}, VALID_CONFIG["api_key"], VALID_CONFIG
    )
    assert ok is True
    assert error is None
    assert ext == "t1-recepcao"
    assert number == "11999998888"
