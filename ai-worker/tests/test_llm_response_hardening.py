from unittest.mock import MagicMock, patch
import pytest
from llm_client import extract_response_text, generate


def test_unexpected_response_value_is_safe():
    assert extract_response_text({"response": ["unexpected"]}) == ""
    assert extract_response_text({"response": 123}) == ""


def test_unsafe_ollama_scheme_is_rejected_without_network():
    with pytest.raises(ValueError):
        generate("file:///etc/passwd", "prompt")


def test_too_large_ollama_response_fails_closed():
    fake = MagicMock()
    fake.read.return_value = b"x" * 2_000_001
    fake.__enter__.return_value = fake
    with patch("llm_client.urllib.request.urlopen", return_value=fake):
        with pytest.raises(ValueError, match="2 MB"):
            generate("http://ollama:11434", "prompt")


def test_normal_response_remains_supported():
    fake = MagicMock()
    fake.read.return_value = b'{"response":"ok"}'
    fake.__enter__.return_value = fake
    with patch("llm_client.urllib.request.urlopen", return_value=fake):
        assert generate("http://ollama:11434", "prompt") == "ok"
