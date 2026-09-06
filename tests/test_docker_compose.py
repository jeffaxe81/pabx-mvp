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


def test_admin_api_ami_secret_matches_manager_conf():
    compose = load_compose()
    env = compose["services"]["admin-api"].get("environment", {})
    manager_conf = (PROJECT_ROOT / "asterisk" / "manager.conf").read_text(encoding="utf-8")
    assert env.get("AMI_USERNAME") and f"[{env['AMI_USERNAME']}]" in manager_conf
    assert env.get("AMI_SECRET") and f"secret = {env['AMI_SECRET']}" in manager_conf
