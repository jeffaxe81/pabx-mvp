from summarizer import clean_summary_response, MAX_SUMMARY_CHARS

def test_long_response_is_bounded():
    assert len(clean_summary_response("x" * 50000)) == MAX_SUMMARY_CHARS

def test_invalid_response_is_empty():
    assert clean_summary_response(None) == ""
    assert clean_summary_response({"text": "abc"}) == ""
