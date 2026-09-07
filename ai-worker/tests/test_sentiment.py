from sentiment import build_sentiment_prompt, parse_sentiment_response

TRANSCRIPT = "Estou muito insatisfeito, já é a terceira vez que ligo sobre isso."


def test_build_sentiment_prompt_includes_transcript_and_instructions():
    prompt = build_sentiment_prompt(TRANSCRIPT)
    assert TRANSCRIPT in prompt
    assert "positivo" in prompt
    assert "negativo" in prompt
    assert "neutro" in prompt


def test_parse_sentiment_exact_match():
    assert parse_sentiment_response("negativo") == "negativo"
    assert parse_sentiment_response("positivo") == "positivo"
    assert parse_sentiment_response("neutro") == "neutro"


def test_parse_sentiment_case_insensitive():
    assert parse_sentiment_response("Negativo") == "negativo"
    assert parse_sentiment_response("POSITIVO") == "positivo"


def test_parse_sentiment_extracts_word_from_longer_response():
    """Modelos nem sempre obedecem 'responda só uma palavra'."""
    assert parse_sentiment_response("Eu diria que o sentimento é negativo, pois o cliente reclamou.") == "negativo"


def test_parse_sentiment_returns_indefinido_when_no_match():
    assert parse_sentiment_response("não sei dizer") == "indefinido"
    assert parse_sentiment_response("") == "indefinido"


def test_parse_sentiment_does_not_crash_on_unexpected_input():
    assert parse_sentiment_response("###!!!") == "indefinido"
