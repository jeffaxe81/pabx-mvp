from transcription import is_supported_audio_file


def test_accepts_supported_extensions():
    assert is_supported_audio_file("gravacao.wav") is True
    assert is_supported_audio_file("gravacao.mp3") is True
    assert is_supported_audio_file("gravacao.gsm") is True


def test_rejects_unsupported_extensions():
    assert is_supported_audio_file("documento.txt") is False
    assert is_supported_audio_file("script.py") is False


def test_case_insensitive():
    assert is_supported_audio_file("GRAVACAO.WAV") is True


def test_handles_path_without_extension():
    assert is_supported_audio_file("arquivo-sem-extensao") is False


# ---------- get_whisper_model (com pywhispercpp mockado) ----------

def test_get_whisper_model_calls_pywhispercpp_and_caches():
    """
    Backlog #47 (migração faster-whisper -> whisper.cpp): confirma
    que a troca de motor realmente aconteceu (chama pywhispercpp, não
    mais faster_whisper) e que o modelo é cacheado - carregar de novo
    a cada transcrição seria caro demais.
    """
    import sys
    from unittest.mock import MagicMock, patch

    fake_model_module = MagicMock()
    fake_model_instance = MagicMock()
    fake_model_module.Model.return_value = fake_model_instance

    with patch.dict(sys.modules, {"pywhispercpp": MagicMock(), "pywhispercpp.model": fake_model_module}):
        import transcription
        transcription._model_cache.clear()

        model1 = transcription.get_whisper_model("base")
        model2 = transcription.get_whisper_model("base")

        assert model1 is model2  # cacheado, não recarrega
        fake_model_module.Model.assert_called_once_with("base", n_threads=4)
