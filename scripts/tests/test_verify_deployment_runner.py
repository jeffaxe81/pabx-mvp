"""
Testes do verify_deployment.py - a parte de rede (AMI/HTTP) é
mockada, já que não há Asterisk/serviços de verdade rodando neste
ambiente. A parte de arquivo (check_secrets) usa arquivos temporários
reais, sem tocar o repositório.
"""
from unittest.mock import patch, MagicMock

import verify_deployment


# ---------- check_secrets ----------

def test_check_secrets_uses_real_files(tmp_path, monkeypatch):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text('AMI_SECRET: "SegredoReal"\n', encoding="utf-8")
    monkeypatch.setattr(verify_deployment, "SECRET_FILES", [compose])

    result = verify_deployment.check_secrets()
    assert result["ok"] is True


def test_check_secrets_flags_remaining_placeholder(tmp_path, monkeypatch):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text('AMI_SECRET: "troque_esta_senha_ami"\n', encoding="utf-8")
    monkeypatch.setattr(verify_deployment, "SECRET_FILES", [compose])

    result = verify_deployment.check_secrets()
    assert result["ok"] is False


def test_check_secrets_skips_missing_files(tmp_path, monkeypatch):
    monkeypatch.setattr(verify_deployment, "SECRET_FILES", [tmp_path / "nao-existe.yml"])
    result = verify_deployment.check_secrets()
    assert result["ok"] is True  # nada encontrado = nada pra reclamar


# ---------- check_ami_login ----------

def test_check_ami_login_accepts_successful_response():
    mock_socket = MagicMock()
    mock_socket.recv.side_effect = [
        b"Asterisk Call Manager/8.0.0\r\n",  # banner
        b"Response: Success\r\nMessage: Authentication accepted\r\n\r\n",
    ]
    mock_socket.__enter__.return_value = mock_socket

    with patch("verify_deployment.socket.create_connection", return_value=mock_socket):
        assert verify_deployment.check_ami_login("queue-api", "segredo-certo") is True


def test_check_ami_login_rejects_failed_response():
    mock_socket = MagicMock()
    mock_socket.recv.side_effect = [
        b"Asterisk Call Manager/8.0.0\r\n",
        b"Response: Error\r\nMessage: Authentication failed\r\n\r\n",
    ]
    mock_socket.__enter__.return_value = mock_socket

    with patch("verify_deployment.socket.create_connection", return_value=mock_socket):
        assert verify_deployment.check_ami_login("queue-api", "segredo-errado") is False


def test_check_ami_login_handles_connection_failure_gracefully():
    """Asterisk fora do ar/porta fechada - não pode lançar exceção, só reportar falha."""
    with patch("verify_deployment.socket.create_connection", side_effect=OSError("conexão recusada")):
        assert verify_deployment.check_ami_login("queue-api", "qualquer") is False


# ---------- check_http_services ----------

def test_check_http_services_reports_all_healthy():
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.__enter__.return_value = mock_response

    with patch("verify_deployment.urllib.request.urlopen", return_value=mock_response):
        result = verify_deployment.check_http_services()

    assert result["all_healthy"] is True
    assert set(result["healthy"]) == set(verify_deployment.HTTP_SERVICES)


def test_check_http_services_reports_connection_failures_as_unhealthy():
    with patch("verify_deployment.urllib.request.urlopen", side_effect=ConnectionError("fora do ar")):
        result = verify_deployment.check_http_services()

    assert result["all_healthy"] is False
    assert all(code is None for code in result["unhealthy"].values())

# ---------- AMI hardening ----------

def test_check_ami_login_accepts_fragmented_response():
    mock_socket = MagicMock()
    mock_socket.recv.side_effect = [
        b"Asterisk Call Manager/8.0.0\r\n",
        b"Response: Suc",
        b"cess\r\nMessage: Authentication accepted\r\n\r\n",
    ]
    mock_socket.__enter__.return_value = mock_socket
    with patch("verify_deployment.socket.create_connection", return_value=mock_socket):
        assert verify_deployment.check_ami_login("queue-api", "segredo") is True
    assert mock_socket.sendall.call_count == 1


def test_check_ami_login_rejects_incomplete_response():
    mock_socket = MagicMock()
    mock_socket.recv.side_effect = [
        b"Asterisk Call Manager/8.0.0\r\n",
        b"Response: Success\r\nMessage: Authentication accepted",
        b"",
    ]
    mock_socket.__enter__.return_value = mock_socket
    with patch("verify_deployment.socket.create_connection", return_value=mock_socket):
        assert verify_deployment.check_ami_login("queue-api", "segredo") is False


def test_check_ami_login_never_sends_header_injection():
    with patch("verify_deployment.socket.create_connection") as connect:
        assert verify_deployment.check_ami_login("queue-api", "x\r\nAction: Command") is False
        assert verify_deployment.check_ami_login("queue-api\nAction", "segredo") is False
        assert verify_deployment.check_ami_login("queue-api", "") is False
    connect.assert_not_called()


def test_check_ami_login_refuses_oversize_response():
    mock_socket = MagicMock()
    mock_socket.recv.side_effect = [
        b"Asterisk Call Manager/8.0.0\r\n",
        b"x" * 17000,
    ]
    mock_socket.__enter__.return_value = mock_socket
    with patch("verify_deployment.socket.create_connection", return_value=mock_socket):
        assert verify_deployment.check_ami_login("queue-api", "segredo") is False


def test_main_reads_ami_secret_without_terminal_echo(capsys):
    with (
        patch("verify_deployment.getpass", return_value="segredo-oculto") as prompt,
        patch("verify_deployment.check_secrets", return_value={"ok": True, "remaining": {}}),
        patch("verify_deployment.check_ami_login", return_value=True) as login,
        patch("verify_deployment.check_http_services", return_value={"all_healthy": True, "healthy": ["api"], "unhealthy": {}}),
        patch("verify_deployment.sys.exit") as exit_mock,
    ):
        verify_deployment.main()
    prompt.assert_called_once()
    login.assert_called_once_with("queue-api", "segredo-oculto")
    exit_mock.assert_called_once_with(0)
    assert "segredo-oculto" not in capsys.readouterr().out
