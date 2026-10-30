from sentiment import parse_sentiment_response

def test_no_substring_false_positive():
    assert parse_sentiment_response("positividade") == "indefinido"

def test_first_word_stable_and_invalid_input():
    assert parse_sentiment_response("neutro, não negativo") == "neutro"
    assert parse_sentiment_response("negativo ou positivo") == "negativo"
    assert parse_sentiment_response(None) == "indefinido"
