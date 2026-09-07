from unittest.mock import MagicMock

from pipeline import process_recording


def test_full_pipeline_with_good_transcript():
    fake_transcribe = MagicMock(return_value="Cliente ligou reclamando do atraso na entrega do pedido 123.")
    fake_llm = MagicMock(side_effect=["Resumo: cliente reclamou de atraso no pedido 123.", "negativo"])

    result = process_recording(
        "20240101-100000-5511999998888-1000.wav",
        filename="20240101-100000-5511999998888-1000.wav",
        ollama_url="http://ollama:11434",
        transcribe_fn=fake_transcribe,
        llm_fn=fake_llm,
    )

    assert result["transcript"].startswith("Cliente ligou")
    assert result["summary"] == "cliente reclamou de atraso no pedido 123."
    assert result["sentiment"] == "negativo"
    assert fake_llm.call_count == 2  # uma pro resumo, uma pro sentimento


def test_pipeline_skips_llm_calls_for_short_transcript():
    fake_transcribe = MagicMock(return_value="alo")
    fake_llm = MagicMock()

    result = process_recording(
        "curta.wav", filename="curta.wav", ollama_url="http://ollama:11434",
        transcribe_fn=fake_transcribe, llm_fn=fake_llm,
    )

    assert result["summary"] is None
    assert result["sentiment"] is None
    fake_llm.assert_not_called()


def test_pipeline_rejects_unsupported_file_format():
    fake_transcribe = MagicMock()
    fake_llm = MagicMock()

    result = process_recording(
        "documento.txt", filename="documento.txt", ollama_url="http://ollama:11434",
        transcribe_fn=fake_transcribe, llm_fn=fake_llm,
    )

    assert "error" in result
    fake_transcribe.assert_not_called()
    fake_llm.assert_not_called()


def test_pipeline_result_always_includes_filename():
    fake_transcribe = MagicMock(return_value="")
    result = process_recording(
        "x.wav", filename="x.wav", ollama_url="http://ollama:11434",
        transcribe_fn=fake_transcribe, llm_fn=MagicMock(),
    )
    assert result["filename"] == "x.wav"
