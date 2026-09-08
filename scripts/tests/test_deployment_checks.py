from deployment_checks import (
    check_no_placeholder_secrets, parse_ami_login_result, summarize_http_health_checks,
)


# ---------- check_no_placeholder_secrets ----------

def test_ok_when_no_placeholders_anywhere():
    result = check_no_placeholder_secrets({
        "docker-compose.yml": 'AMI_SECRET: "SegredoReal123"\n',
        "manager.conf": "secret = SegredoReal123\n",
    })
    assert result["ok"] is True
    assert result["remaining"] == {}


def test_reports_remaining_placeholders_by_file():
    result = check_no_placeholder_secrets({
        "docker-compose.yml": 'AMI_SECRET: "troque_esta_senha_ami"\n',
        "manager.conf": "secret = SegredoReal123\n",
    })
    assert result["ok"] is False
    assert result["remaining"] == {"docker-compose.yml": {"troque_esta_senha_ami"}}


def test_only_files_with_placeholders_appear_in_report():
    """Um arquivo limpo não deveria poluir o relatório com uma entrada vazia."""
    result = check_no_placeholder_secrets({
        "a.conf": "tudo certo por aqui\n",
        "b.conf": "troque_esta_senha_x\n",
    })
    assert "a.conf" not in result["remaining"]
    assert "b.conf" in result["remaining"]


def test_ok_with_empty_input():
    result = check_no_placeholder_secrets({})
    assert result["ok"] is True


# ---------- parse_ami_login_result ----------

def test_recognizes_successful_login():
    assert parse_ami_login_result("Response: Success\r\nMessage: Authentication accepted\r\n\r\n") is True


def test_recognizes_failed_login():
    assert parse_ami_login_result("Response: Error\r\nMessage: Authentication failed\r\n\r\n") is False


def test_handles_empty_response():
    assert parse_ami_login_result("") is False


def test_tolerates_leading_whitespace_before_response_line():
    """.strip() já cobre isso - resposta com espaço/quebra de linha antes ainda é reconhecida."""
    assert parse_ami_login_result("\r\n  Response: Success\r\n") is True


# ---------- summarize_http_health_checks ----------

def test_all_healthy_when_everyone_returns_200():
    result = summarize_http_health_checks({"queue-api": 200, "admin-api": 200})
    assert result["all_healthy"] is True
    assert result["unhealthy"] == {}


def test_reports_unhealthy_services():
    result = summarize_http_health_checks({"queue-api": 200, "admin-api": 503, "ai-worker": None})
    assert result["all_healthy"] is False
    assert result["unhealthy"] == {"admin-api": 503, "ai-worker": None}
    assert result["healthy"] == ["queue-api"]


def test_healthy_list_is_sorted():
    result = summarize_http_health_checks({"z-service": 200, "a-service": 200})
    assert result["healthy"] == ["a-service", "z-service"]
