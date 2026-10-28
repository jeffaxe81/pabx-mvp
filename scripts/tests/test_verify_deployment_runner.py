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


def test_check_secrets_blocks_missing_files(tmp_path, monkeypatch):
    missing = tmp_path / "nao-existe.yml"
    monkeypatch.setattr(verify_deployment, "SECRET_FILES", [missing])
    result = verify_deployment.check_secrets()
    assert result["ok"] is False
    assert result["unavailable"] == [str(missing)]
    assert result["remaining"] == {}


def test_check_secrets_blocks_missing_file_even_if_others_are_clean(tmp_path, monkeypatch):
    present = tmp_path / "manager.conf"
    missing = tmp_path / "docker-compose.yml"
    present.write_text("secret = seguro\n", encoding="utf-8")
    monkeypatch.setattr(verify_deployment, "SECRET_FILES", [present, missing])
    result = verify_deployment.check_secrets()
    assert result["ok"] is False
    assert result["unavailable"] == [str(missing)]


def test_check_secrets_blocks_empty_file(tmp_path, monkeypatch):
    file = tmp_path / "pjsip.conf"
    file.write_text(" \n  ", encoding="utf-8")
    monkeypatch.setattr(verify_deployment, "SECRET_FILES", [file])
    result = verify_deployment.check_secrets()
    assert result["ok"] is False
    assert str(file) in result["unavailable"]


def test_check_secrets_blocks_invalid_encoding(tmp_path, monkeypatch):
    file = tmp_path / "manager.conf"
    file.write_bytes(b"\xff")
    monkeypatch.setattr(verify_deployment, "SECRET_FILES", [file])
    result = verify_deployment.check_secrets()
    assert result["ok"] is False
    assert str(file) in result["unavailable"]


def test_check_secrets_blocks_empty_required_file_list(monkeypatch):
    monkeypatch.setattr(verify_deployment, "SECRET_FILES", [])
    result = verify_deployment.check_secrets()
    assert result["ok"] is False
    assert result["unavailable"] == []


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
    from urllib.error import HTTPError

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.__enter__.return_value = mock_response

    def fake_urlopen(url, timeout=5):
        if url.endswith("/api/queue"):
            raise HTTPError(url, 401, "Unauthorized", {"WWW-Authenticate": "Bearer"}, None)
        return mock_response

    with patch("verify_deployment.urllib.request.urlopen", side_effect=fake_urlopen):
        result = verify_deployment.check_http_services()

    assert result["all_healthy"] is True
    assert set(result["healthy"]) == set(verify_deployment.HTTP_SERVICES)


def test_check_http_services_does_not_accept_unprotected_queue_endpoint():
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.__enter__.return_value = mock_response

    with patch("verify_deployment.urllib.request.urlopen", return_value=mock_response):
        result = verify_deployment.check_http_services()

    assert result["all_healthy"] is False
    assert result["unhealthy"]["queue-api"] == 200


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


def test_main_reports_missing_config_without_exposing_any_secret(capsys, tmp_path):
    missing = str(tmp_path / "manager.conf")
    result = {"ok": False, "remaining": {}, "unavailable": [missing]}
    with (
        patch("verify_deployment.getpass", return_value="segredo-oculto"),
        patch("verify_deployment.check_secrets", return_value=result),
        patch("verify_deployment.check_ami_login", return_value=True),
        patch("verify_deployment.check_http_services", return_value={"all_healthy": True, "healthy": ["api"], "unhealthy": {}}),
        patch("verify_deployment.sys.exit") as finish,
    ):
        verify_deployment.main()
    output = capsys.readouterr().out
    assert "Arquivo ausente, vazio ou ilegível" in output
    assert missing in output
    assert "segredo-oculto" not in output
    finish.assert_called_once_with(1)

def test_verifier_rejects_static_voicemail_placeholders(tmp_path, monkeypatch):
    voicemail = tmp_path / "voicemail.conf"
    voicemail.write_text(
        "[t1]\nt1-1001 => troque_esta_senha_vm_t1_1001,T1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(verify_deployment, "SECRET_FILES", [voicemail])
    result = verify_deployment.check_secrets()
    assert result["ok"] is False
    assert str(voicemail) in result["remaining"]

