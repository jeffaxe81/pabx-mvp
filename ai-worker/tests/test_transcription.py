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
