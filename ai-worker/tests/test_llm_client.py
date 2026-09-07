from unittest.mock import patch, MagicMock

from llm_client import build_generate_request, extract_response_text, generate


# ---------- build_generate_request ----------

def test_build_generate_request_basic_fields():
    req = build_generate_request("resuma isso", model="llama3")
    assert req["model"] == "llama3"
    assert req["prompt"] == "resuma isso"
    assert req["stream"] is False


def test_build_generate_request_uses_low_temperature_by_default():
    req = build_generate_request("qualquer coisa")
    assert req["options"]["temperature"] <= 0.5


def test_build_generate_request_custom_model():
    req = build_generate_request("prompt", model="llama3:70b")
    assert req["model"] == "llama3:70b"


# ---------- extract_response_text ----------

def test_extract_response_text_returns_response_field():
    assert extract_response_text({"response": "  texto gerado  "}) == "texto gerado"


def test_extract_response_text_missing_field_returns_empty():
    assert extract_response_text({}) == ""


def test_extract_response_text_handles_non_dict_gracefully():
    assert extract_response_text(None) == ""
    assert extract_response_text("string qualquer") == ""
    assert extract_response_text([1, 2, 3]) == ""


# ---------- generate (rede mockada) ----------

def test_generate_sends_request_and_parses_response():
    fake_response_body = b'{"response": "resumo da chamada aqui"}'

    mock_http_response = MagicMock()
    mock_http_response.read.return_value = fake_response_body
    mock_http_response.__enter__.return_value = mock_http_response

    with patch("llm_client.urllib.request.urlopen", return_value=mock_http_response) as mock_urlopen:
        result = generate("http://ollama:11434", "resuma: ...", model="llama3")

    assert result == "resumo da chamada aqui"
    mock_urlopen.assert_called_once()


def test_generate_strips_trailing_slash_from_base_url():
    fake_response_body = b'{"response": "ok"}'
    mock_http_response = MagicMock()
    mock_http_response.read.return_value = fake_response_body
    mock_http_response.__enter__.return_value = mock_http_response

    with patch("llm_client.urllib.request.urlopen", return_value=mock_http_response) as mock_urlopen:
        generate("http://ollama:11434/", "prompt")

    called_request = mock_urlopen.call_args[0][0]
    assert called_request.full_url == "http://ollama:11434/api/generate"
