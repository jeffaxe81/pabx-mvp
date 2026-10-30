from intent_classifier import parse_intent_response

def test_no_partial_word_match():
    assert parse_intent_response("suportezinho") == "outro"
    assert parse_intent_response("vendasx") == "outro"

def test_conflicting_labels_fallback():
    assert parse_intent_response("vendas ou suporte") == "outro"
    assert parse_intent_response(None) == "outro"
    assert parse_intent_response("Classifico como suporte.") == "suporte"
