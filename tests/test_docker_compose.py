"""
Testes estáticos do docker-compose.yml: garante que os serviços,
portas e volumes esperados não sumiram numa refatoração futura.
"""
from pathlib import Path

import yaml

COMPOSE_PATH = Path(__file__).parent.parent / "docker-compose.yml"
PROJECT_ROOT = Path(__file__).parent.parent


def load_compose():
    return yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))


def test_compose_is_valid_yaml():
    compose = load_compose()
    assert "services" in compose


def test_expected_services_present():
    compose = load_compose()
    services = compose["services"]
    for expected in ("asterisk", "provisioning", "webphone", "queue-api"):
        assert expected in services, f"Serviço '{expected}' ausente no docker-compose.yml"


def test_asterisk_volumes_point_to_existing_files():
    """
    Cada arquivo montado como volume no serviço asterisk precisa
    existir de verdade no repositório, senão o container falha ao
    subir com erro de mount.
    """
    compose = load_compose()
    volumes = compose["services"]["asterisk"].get("volumes", [])
    for volume in volumes:
        host_path = volume.split(":")[0]
        if host_path.startswith("./"):
            resolved = PROJECT_ROOT / host_path[2:]
            assert resolved.exists(), f"Volume referencia caminho inexistente: {host_path}"


def test_webphone_service_exposes_a_port():
    compose = load_compose()
    ports = compose["services"]["webphone"].get("ports", [])
    assert ports, "Serviço webphone precisa expor uma porta para o navegador acessar"


def test_provisioning_service_serves_files_directory():
    compose = load_compose()
    volumes = compose["services"]["provisioning"].get("volumes", [])
    assert any("provisioning/files" in v for v in volumes), (
        "Serviço provisioning deveria servir a pasta provisioning/files"
    )


def test_queue_api_env_matches_manager_conf_credentials():
    """
    A senha de AMI usada pelo queue-api no compose precisa bater com a
    configurada em manager.conf - senão o serviço sobe e nunca
    consegue logar (falha silenciosa em produção, chata de debugar).
    """
    compose = load_compose()
    env = compose["services"]["queue-api"].get("environment", {})

    manager_conf = (PROJECT_ROOT / "asterisk" / "manager.conf").read_text(encoding="utf-8")
    assert env.get("AMI_USERNAME") and f"[{env['AMI_USERNAME']}]" in manager_conf
    assert env.get("AMI_SECRET") and f"secret = {env['AMI_SECRET']}" in manager_conf


def test_recordings_volume_shared_between_asterisk_and_queue_api():
    """
    Asterisk escreve as gravações, queue-api precisa conseguir ler os
    mesmos arquivos - os dois precisam apontar pro mesmo caminho no
    host (./recordings).
    """
    compose = load_compose()
    asterisk_volumes = compose["services"]["asterisk"].get("volumes", [])
    queue_api_volumes = compose["services"]["queue-api"].get("volumes", [])

    assert any(v.startswith("./recordings:") for v in asterisk_volumes)
    assert any(v.startswith("./recordings:") for v in queue_api_volumes)


def test_recordings_volume_is_writable_for_retention_cleanup():
    """
    Expurgo automático (backlog #15) precisa apagar arquivo - se o
    volume estiver montado só leitura (:ro), a função de retenção
    falharia silenciosamente sempre que fosse rodar de verdade.
    """
    compose = load_compose()
    queue_api_volumes = compose["services"]["queue-api"].get("volumes", [])
    recordings_volume = next(v for v in queue_api_volumes if v.startswith("./recordings:"))
    assert not recordings_volume.endswith(":ro")


def test_recordings_retention_disabled_by_default():
    compose = load_compose()
    env = compose["services"]["queue-api"].get("environment", {})
    assert env.get("RECORDINGS_RETENTION_DAYS") == "0"


def test_voicemail_mail_relay_script_mounted_and_disabled_by_default():
    """
    Backlog #16: o script que relaia o e-mail do correio de voz
    precisa estar montado no container do Asterisk, e o SMTP vem
    desligado por padrão (mesmo padrão de segurança das outras
    integrações opt-in do projeto).
    """
    compose = load_compose()
    asterisk_volumes = compose["services"]["asterisk"].get("volumes", [])
    assert any("scripts" in v for v in asterisk_volumes)

    env = compose["services"]["asterisk"].get("environment", {})
    assert env.get("SMTP_HOST") == ""


def test_ura_sounds_mounted_into_asterisk_container():
    """
    Sem esse volume, o Background(custom/menu-principal) do dialplan
    nunca encontraria o arquivo de áudio - a URA "funcionaria"
    silenciosamente sem tocar nada.
    """
    compose = load_compose()
    asterisk_volumes = compose["services"]["asterisk"].get("volumes", [])
    assert any("sounds/custom" in v for v in asterisk_volumes)


def test_notify_channels_env_present_and_disabled_by_default():
    """
    Notificação de chamada perdida deve vir DESLIGADA por padrão (o
    projeto não pode sair enviando email/whatsapp sem credenciais
    reais configuradas) - mas a variável precisa existir pra ficar
    óbvio onde habilitar.
    """
    compose = load_compose()
    env = compose["services"]["queue-api"].get("environment", {})
    assert "NOTIFY_CHANNELS" in env
    assert env["NOTIFY_CHANNELS"] == ""


def test_click_to_call_api_key_disabled_by_default():
    """
    Mesma lógica da notificação: a API que origina chamadas não pode
    vir habilitada por padrão sem uma chave configurada de propósito.
    """
    compose = load_compose()
    env = compose["services"]["queue-api"].get("environment", {})
    assert "CLICK_TO_CALL_API_KEY" in env
    assert env["CLICK_TO_CALL_API_KEY"] == ""
    assert "CLICK_TO_CALL_ALLOWED_EXTENSIONS" in env


def test_cdr_config_files_mounted_for_metrics():
    """
    O dashboard de métricas depende dos eventos CDR - sem esses dois
    arquivos montados, o Asterisk nunca gera os eventos e o painel
    fica sempre zerado, silenciosamente.
    """
    compose = load_compose()
    asterisk_volumes = compose["services"]["asterisk"].get("volumes", [])
    assert any("cdr.conf" in v for v in asterisk_volumes)
    assert any("cdr_manager.conf" in v for v in asterisk_volumes)


def test_admin_api_service_present_and_login_disabled_by_default():
    """
    Painel de administração (backlog #10) precisa existir no compose,
    mas com login desligado até alguém configurar ADMIN_PASSWORD_HASH
    de propósito - mesmo padrão de segurança das outras integrações.
    """
    compose = load_compose()
    assert "admin-api" in compose["services"]
    env = compose["services"]["admin-api"].get("environment", {})
    assert env.get("ADMIN_PASSWORD_HASH") == ""
    assert "USERS_PATH" in env


def test_admin_api_ami_secret_matches_manager_conf():
    compose = load_compose()
    env = compose["services"]["admin-api"].get("environment", {})
    manager_conf = (PROJECT_ROOT / "asterisk" / "manager.conf").read_text(encoding="utf-8")
    assert env.get("AMI_USERNAME") and f"[{env['AMI_USERNAME']}]" in manager_conf
    assert env.get("AMI_SECRET") and f"secret = {env['AMI_SECRET']}" in manager_conf


def test_queue_api_has_persistent_volume_for_call_log():
    """
    O histórico de relatórios (call_log.jsonl) precisa sobreviver a um
    restart do container - senão "relatório por período" não faz
    sentido nenhum (voltaria a zero toda hora).
    """
    compose = load_compose()
    volumes = compose["services"]["queue-api"].get("volumes", [])
    assert any("queue_api_data" in v or "/app/data" in v for v in volumes)
    assert "queue_api_data" in compose.get("volumes", {})


def test_crm_webhook_disabled_by_default():
    """
    Screen-pop pro CRM (backlog #13) não pode sair fazendo POST pra
    lugar nenhum sem alguém configurar a URL de propósito.
    """
    compose = load_compose()
    env = compose["services"]["queue-api"].get("environment", {})
    assert "CRM_WEBHOOK_URL" in env
    assert env["CRM_WEBHOOK_URL"] == ""


def test_fraud_auto_block_and_spending_limit_disabled_by_default():
    """
    Detecção de fraude (backlog #32): alerta pode vir ligado (é só
    visibilidade), mas bloqueio automático e limite de gasto são
    ações com efeito colateral real - precisam vir desligadas até
    alguém configurar de propósito.
    """
    compose = load_compose()
    env = compose["services"]["queue-api"].get("environment", {})
    assert env.get("FRAUD_AUTO_BLOCK") == "false"
    assert env.get("FRAUD_DAILY_COST_LIMIT") == "0"


def test_backup_service_present_and_does_not_mount_docker_socket():
    """
    Backup automático (backlog #33) precisa existir, e de propósito
    NÃO deve montar o socket do Docker - isso equivaleria a dar acesso
    root ao host pro container de backup, um risco desproporcional ao
    benefício (ver manual 28).
    """
    compose = load_compose()
    assert "backup" in compose["services"]
    volumes = compose["services"]["backup"].get("volumes", [])
    assert not any("docker.sock" in v for v in volumes)


def test_backup_service_mounts_both_named_volumes_readonly():
    compose = load_compose()
    volumes = compose["services"]["backup"].get("volumes", [])
    assert any(v.startswith("admin_data:") and v.endswith(":ro") for v in volumes)
    assert any(v.startswith("queue_api_data:") and v.endswith(":ro") for v in volumes)


def test_backup_retention_disabled_by_default():
    compose = load_compose()
    env = compose["services"]["backup"].get("environment", {})
    assert env.get("BACKUP_RETENTION_DAYS") == "0"


def test_quality_monitoring_thresholds_configured():
    """
    Diferente de fraude/backup (opt-in), monitoramento de qualidade é
    só visibilidade - por isso os limiares já vêm com valor ativo por
    padrão, não "0"/"desligado".
    """
    compose = load_compose()
    env = compose["services"]["queue-api"].get("environment", {})
    assert "QUALITY_JITTER_THRESHOLD_MS" in env
    assert "QUALITY_PACKET_LOSS_THRESHOLD_PERCENT" in env
    assert float(env["QUALITY_JITTER_THRESHOLD_MS"]) > 0


def test_campaigns_path_configured():
    compose = load_compose()
    env = compose["services"]["queue-api"].get("environment", {})
    assert "CAMPAIGNS_PATH" in env


def test_callbacks_path_configured():
    compose = load_compose()
    env = compose["services"]["queue-api"].get("environment", {})
    assert "CALLBACKS_PATH" in env
    assert "CALLBACK_CONNECT_CONTEXT" in env


def test_survey_path_configured():
    compose = load_compose()
    env = compose["services"]["queue-api"].get("environment", {})
    assert "SURVEY_PATH" in env
