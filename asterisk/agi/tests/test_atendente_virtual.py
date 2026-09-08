from unittest.mock import patch, MagicMock

from atendente_virtual import classify_intent, FALLBACK_EXTENSION


def test_classify_intent_returns_extension_from_response():
    fake_body = b'{"transcript": "quero comprar um plano novo", "intent": "vendas", "extension": "1000", "confirmation_filename": "tts-abc.wav"}'
    mock_response = MagicMock()
    mock_response.read.return_value = fake_body
    mock_response.__enter__.return_value = mock_response

    with patch("atendente_virtual.urllib.request.urlopen", return_value=mock_response):
        result = classify_intent("intake-123.wav")

    assert result == {"extension": "1000", "confirmation_filename": "tts-abc.wav"}


def test_classify_intent_handles_response_without_confirmation_audio():
    """A confirmação falada é best-effort no ai-worker - pode vir None se a síntese falhar."""
    fake_body = b'{"transcript": "x", "intent": "outro", "extension": "1000", "confirmation_filename": null}'
    mock_response = MagicMock()
    mock_response.read.return_value = fake_body
    mock_response.__enter__.return_value = mock_response

    with patch("atendente_virtual.urllib.request.urlopen", return_value=mock_response):
        result = classify_intent("intake-123.wav")

    assert result["confirmation_filename"] is None


def test_classify_intent_falls_back_on_network_failure():
    """
    Se o ai-worker estiver fora do ar (ou IA desligada, ou qualquer
    outra falha), o atendente virtual NUNCA pode travar a chamada -
    sempre cai no destino seguro (fila geral), sem confirmação falada.
    """
    with patch("atendente_virtual.urllib.request.urlopen", side_effect=ConnectionError("fora do ar")):
        result = classify_intent("intake-123.wav")

    assert result == {"extension": FALLBACK_EXTENSION, "confirmation_filename": None}


def test_classify_intent_falls_back_on_malformed_response():
    mock_response = MagicMock()
    mock_response.read.return_value = b"isso nao e json valido"
    mock_response.__enter__.return_value = mock_response

    with patch("atendente_virtual.urllib.request.urlopen", return_value=mock_response):
        result = classify_intent("intake-123.wav")

    assert result["extension"] == FALLBACK_EXTENSION
    assert result["confirmation_filename"] is None


def test_main_streams_confirmation_before_setting_destination():
    """
    Backlog #48, fase 2: quando há áudio de confirmação, ele precisa
    tocar ANTES da variável de destino ser definida (senão a
    confirmação chegaria tarde demais, depois do roteamento já ter
    sido decidido pelo dialplan).
    """
    import atendente_virtual

    fake_body = (
        b'{"transcript": "x", "intent": "vendas", "extension": "1000", '
        b'"confirmation_filename": "tts-abc123.wav"}'
    )
    mock_response = MagicMock()
    mock_response.read.return_value = fake_body
    mock_response.__enter__.return_value = mock_response

    sent_commands = []

    def fake_send_agi_command(command):
        sent_commands.append(command)
        return {"code": 200, "result": "0", "raw": "200 result=0"}

    with patch("atendente_virtual.urllib.request.urlopen", return_value=mock_response), \
         patch("atendente_virtual.read_agi_env", return_value={"agi_uniqueid": "123.456"}), \
         patch("atendente_virtual.send_agi_command", side_effect=fake_send_agi_command):
        atendente_virtual.main()

    stream_commands = [c for c in sent_commands if c.startswith("STREAM FILE")]
    set_var_commands = [c for c in sent_commands if c.startswith("SET VARIABLE INTENT_DESTINO")]

    assert stream_commands, "deveria ter tocado o áudio de confirmação"
    assert 'custom/tts-abc123' in stream_commands[0]
    assert sent_commands.index(stream_commands[0]) < sent_commands.index(set_var_commands[0])


def test_main_skips_stream_file_when_no_confirmation_available():
    import atendente_virtual

    fake_body = b'{"transcript": "x", "intent": "outro", "extension": "1000", "confirmation_filename": null}'
    mock_response = MagicMock()
    mock_response.read.return_value = fake_body
    mock_response.__enter__.return_value = mock_response

    sent_commands = []

    def fake_send_agi_command(command):
        sent_commands.append(command)
        return {"code": 200, "result": "0", "raw": "200 result=0"}

    with patch("atendente_virtual.urllib.request.urlopen", return_value=mock_response), \
         patch("atendente_virtual.read_agi_env", return_value={"agi_uniqueid": "123.456"}), \
         patch("atendente_virtual.send_agi_command", side_effect=fake_send_agi_command):
        atendente_virtual.main()

    stream_commands = [c for c in sent_commands if c.startswith("STREAM FILE")]
    assert not stream_commands
