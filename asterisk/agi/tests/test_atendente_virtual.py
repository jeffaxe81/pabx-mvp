from unittest.mock import patch, MagicMock

from atendente_virtual import classify_intent, FALLBACK_EXTENSION


def test_classify_intent_returns_extension_from_response():
    fake_body = b'{"transcript": "quero comprar um plano novo", "intent": "vendas", "extension": "1000"}'
    mock_response = MagicMock()
    mock_response.read.return_value = fake_body
    mock_response.__enter__.return_value = mock_response

    with patch("atendente_virtual.urllib.request.urlopen", return_value=mock_response):
        result = classify_intent("intake-123.wav")

    assert result == "1000"


def test_classify_intent_falls_back_on_network_failure():
    """
    Se o ai-worker estiver fora do ar (ou IA desligada, ou qualquer
    outra falha), o atendente virtual NUNCA pode travar a chamada -
    sempre cai no destino seguro (fila geral).
    """
    with patch("atendente_virtual.urllib.request.urlopen", side_effect=ConnectionError("fora do ar")):
        result = classify_intent("intake-123.wav")

    assert result == FALLBACK_EXTENSION


def test_classify_intent_falls_back_on_malformed_response():
    mock_response = MagicMock()
    mock_response.read.return_value = b"isso nao e json valido"
    mock_response.__enter__.return_value = mock_response

    with patch("atendente_virtual.urllib.request.urlopen", return_value=mock_response):
        result = classify_intent("intake-123.wav")

    assert result == FALLBACK_EXTENSION
