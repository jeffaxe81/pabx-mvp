from summarizer import build_summary_prompt, is_transcript_worth_summarizing, clean_summary_response

LONG_TRANSCRIPT = "Cliente ligou perguntando sobre o status do pedido 12345 e a atendente confirmou envio pra amanhã."


def test_build_summary_prompt_includes_transcript():
    prompt = build_summary_prompt(LONG_TRANSCRIPT)
    assert LONG_TRANSCRIPT in prompt
    assert "resumo" in prompt.lower() or "Resumo" in prompt


def test_worth_summarizing_true_for_long_transcript():
    assert is_transcript_worth_summarizing(LONG_TRANSCRIPT) is True


def test_worth_summarizing_false_for_empty_or_short():
    assert is_transcript_worth_summarizing("") is False
    assert is_transcript_worth_summarizing(None) is False
    assert is_transcript_worth_summarizing("oi") is False


def test_clean_summary_response_removes_common_prefixes():
    assert clean_summary_response("Resumo: cliente ligou pra X") == "cliente ligou pra X"
    assert clean_summary_response("**Resumo:** cliente ligou pra X") == "cliente ligou pra X"


def test_clean_summary_response_strips_quotes():
    assert clean_summary_response('"cliente ligou pra X"') == "cliente ligou pra X"


def test_clean_summary_response_leaves_normal_text_untouched():
    assert clean_summary_response("Cliente ligou pra X.") == "Cliente ligou pra X."
