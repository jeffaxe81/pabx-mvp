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
    for expected in ("asterisk", "provisioning", "webphone"):
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
