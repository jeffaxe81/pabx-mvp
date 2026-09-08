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
