"""Provas estaticas: servidor .cfg HTTP nunca inicia no Compose padrao."""
import copy
import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "provisioning_exposure_preflight",
    ROOT / "scripts" / "provisioning_exposure_preflight.py",
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def original():
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))


def test_default_denies_exposure_and_marks_production_no_go():
    result = module.check_configuration(original())
    assert result["default_compose_starts_insecure_http"] is False
    assert result["bind_only_loopback"] is True
    assert result["profile_requires_explicit_opt_in"] is True
    assert result["http_lab_provisioning_secure"] is False
    assert result["tls_authentication_implemented_by_this_change"] is False
    assert result["real_yealink_tested"] is False
    assert result["production_go_authorized"] is False


def test_legacy_profile_is_off_by_default_and_not_auto_restarted():
    service = original()["services"]["provisioning"]
    assert service["profiles"] == ["insecure-lab-provisioning"]
    assert service["restart"] == "no"
    assert service["ports"] == ["127.0.0.1:8080:80"]
    assert service["volumes"] == [
        "./provisioning/files:/usr/share/nginx/html:ro"
    ]


@pytest.mark.parametrize("profile", [
    None, [], ["default"], ["prod"], ["insecure-lab-provisioning", "default"],
    "insecure-lab-provisioning",
])
def test_missing_implicit_or_extra_profile_rejected(profile):
    config = original()
    if profile is None:
        config["services"]["provisioning"].pop("profiles")
    else:
        config["services"]["provisioning"]["profiles"] = profile
    with pytest.raises(ValueError, match="PERFIL"):
        module.check_configuration(config)


@pytest.mark.parametrize("port", [
    "8080:80", "0.0.0.0:8080:80", "[::]:8080:80",
    "192.168.0.1:8080:80", "127.0.0.1:70000:80",
    "127.0.0.1:8080:443", "127.0.0.1:8080:80/udp",
    8080, {"published": 8080, "target": 80},
])
def test_unexpected_port_or_bind_rejected(port):
    config = original()
    config["services"]["provisioning"]["ports"] = [port]
    with pytest.raises(ValueError, match="PORTA"):
        module.check_configuration(config)


def test_empty_and_multiple_ports_rejected():
    for ports in ([], ["127.0.0.1:8080:80", "8081:80"], None):
        config = original()
        config["services"]["provisioning"]["ports"] = ports
        with pytest.raises(ValueError):
            module.check_configuration(config)


@pytest.mark.parametrize("volumes", [
    [], ["./provisioning/files:/usr/share/nginx/html"],
    ["./provisioning/files:/usr/share/nginx/html:rw"],
    ["./provisioning/files:/usr/share/nginx/html:ro", "/tmp:/tmp:ro"],
])
def test_missing_writable_or_extra_mount_rejected(volumes):
    config = original()
    config["services"]["provisioning"]["volumes"] = volumes
    with pytest.raises(ValueError, match="MOUNT"):
        module.check_configuration(config)


@pytest.mark.parametrize("restart", ["always", "unless-stopped", None, True])
def test_insecure_service_cannot_auto_restart(restart):
    config = original()
    config["services"]["provisioning"]["restart"] = restart
    with pytest.raises(ValueError, match="RESTART"):
        module.check_configuration(config)


def test_network_mode_host_rejected():
    config = original()
    config["services"]["provisioning"]["network_mode"] = "host"
    with pytest.raises(ValueError, match="NETWORK"):
        module.check_configuration(config)


def test_other_service_cannot_publish_confidential_folder():
    config = original()
    config["services"]["webphone"]["volumes"].append(
        "./provisioning/files:/usr/share/nginx/html:ro"
    )
    with pytest.raises(ValueError, match="EXTRA"):
        module.check_configuration(config)


def test_invalid_compose_documents_rejected():
    for document in (None, [], {}, {"services": {}}, {"services": []},
                     {"services": {"provisioning": "not an object"}}):
        with pytest.raises(ValueError):
            module.check_configuration(document)


def test_preflight_rejects_symlink_oversized_and_malformed_yaml(tmp_path):
    target = tmp_path / "compose.yml"
    target.write_text("services: [", encoding="utf-8")
    assert module.main(["--compose", str(target)]) == 2
    target.write_bytes(b"x" * (module.MAX_COMPOSE_BYTES + 1))
    assert module.main(["--compose", str(target)]) == 2
    link = tmp_path / "symlink.yml"
    link.symlink_to(target)
    assert module.main(["--compose", str(link)]) == 2


def test_preflight_cli_reports_sanitized_no_go(capsys):
    assert module.main([]) == 0
    out = capsys.readouterr().out
    assert "INSECURE_LAB_ONLY_DEFAULT_DENY" in out
    assert '"production_go_authorized": false' in out
