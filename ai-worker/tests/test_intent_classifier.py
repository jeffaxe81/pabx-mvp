from intent_classifier import build_intent_prompt, parse_intent_response, intent_to_extension


# ---------- build_intent_prompt ----------

def test_build_intent_prompt_includes_transcript():
    prompt = build_intent_prompt("quero saber sobre os planos disponíveis")
    assert "quero saber sobre os planos disponíveis" in prompt
    assert "vendas" in prompt
    assert "suporte" in prompt


# ---------- parse_intent_response ----------

def test_parse_intent_exact_match():
    assert parse_intent_response("vendas") == "vendas"
    assert parse_intent_response("suporte") == "suporte"
    assert parse_intent_response("outro") == "outro"


def test_parse_intent_case_insensitive():
    assert parse_intent_response("Vendas") == "vendas"
    assert parse_intent_response("SUPORTE") == "suporte"


def test_parse_intent_extracts_from_longer_response():
    assert parse_intent_response("Eu classificaria isso como suporte, já que é um problema.") == "suporte"


def test_parse_intent_defaults_to_outro_when_unclear():
    assert parse_intent_response("não tenho certeza") == "outro"
    assert parse_intent_response("") == "outro"
    assert parse_intent_response("###") == "outro"


def test_parse_intent_finds_match_anywhere_in_response():
    assert parse_intent_response("A resposta correta aqui é: suporte técnico") == "suporte"


# ---------- intent_to_extension ----------

def test_intent_to_extension_known_intents():
    assert intent_to_extension("vendas") == "1000"
    assert intent_to_extension("suporte") == "1010"


def test_intent_to_extension_unknown_falls_back_to_outro_destination():
    assert intent_to_extension("intencao-desconhecida") == intent_to_extension("outro")


def test_intent_to_extension_never_returns_none():
    for intent in ("vendas", "suporte", "outro", "", "lixo", None):
        assert intent_to_extension(intent) is not None


# ---------- build_confirmation_phrase ----------

def test_build_confirmation_phrase_known_intents():
    from intent_classifier import build_confirmation_phrase
    assert "vendas" in build_confirmation_phrase("vendas").lower()
    assert "suporte" in build_confirmation_phrase("suporte").lower()


def test_build_confirmation_phrase_never_returns_empty():
    from intent_classifier import build_confirmation_phrase
    for intent in ("vendas", "suporte", "outro", "", "lixo", None):
        phrase = build_confirmation_phrase(intent)
        assert phrase and isinstance(phrase, str)


def test_build_confirmation_phrase_unknown_intent_falls_back_to_outro():
    from intent_classifier import build_confirmation_phrase
    assert build_confirmation_phrase("intencao-desconhecida") == build_confirmation_phrase("outro")
