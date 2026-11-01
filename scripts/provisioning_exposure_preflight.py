#!/usr/bin/env python3
"""Gate offline para detectar exposição HTTP de arquivos .cfg com senhas SIP.

Não ativa serviços, não autentica telefones e não valida interoperabilidade.
Um PASS comprova apenas que o Nginx legado está opt-in e vinculado ao loopback.
Produção e telefones físicos permanecem NO-GO (issue #344).
"""
import argparse
import json
from pathlib import Path
import re
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
MAX_COMPOSE_BYTES = 1024 * 1024
LOOPBACK_PORT = re.compile(r"127\.0\.0\.1:([1-9][0-9]{0,4}):80\Z")
EXPECTED_MOUNT = "./provisioning/files:/usr/share/nginx/html:ro"
PROFILE = "insecure-lab-provisioning"


def check_configuration(config):
    if not isinstance(config, dict) or not isinstance(config.get("services"), dict):
        raise ValueError("COMPOSE-INVALIDO")
    services = config["services"]
    if not services:
        raise ValueError("COMPOSE-SERVICOS-VAZIOS")
    # Nenhum outro servico do mesmo Compose pode publicar a mesma pasta
    # confidencial sem as protecoes exigidas. Nao segue redirecionamentos.
    for name, item in services.items():
        if not isinstance(name, str) or not isinstance(item, dict):
            raise ValueError("COMPOSE-SERVICO-INVALIDO")
        volumes = item.get("volumes", [])
        if not isinstance(volumes, list):
            raise ValueError("COMPOSE-VOLUMES-INVALIDOS")
        if name != "provisioning" and any(
            isinstance(volume, str) and (
                volume.startswith("./provisioning/files:")
                or volume.startswith("provisioning/files:")
            ) for volume in volumes
        ):
            raise ValueError("PROVISIONING-MOUNT-EXTRA")

    service = services.get("provisioning")
    if not isinstance(service, dict):
        raise ValueError("PROVISIONING-SERVICO-AUSENTE")
    if service.get("profiles") != [PROFILE]:
        raise ValueError("PROVISIONING-PERFIL-OBRIGATORIO")
    if service.get("network_mode") is not None:
        raise ValueError("PROVISIONING-NETWORK-MODE")
    if service.get("restart") != "no":
        raise ValueError("PROVISIONING-RESTART")
    if service.get("volumes") != [EXPECTED_MOUNT]:
        raise ValueError("PROVISIONING-MOUNT-READONLY")
    ports = service.get("ports")
    if not isinstance(ports, list) or len(ports) != 1 or not isinstance(ports[0], str):
        raise ValueError("PROVISIONING-PORTAS-INVALIDAS")
    match = LOOPBACK_PORT.fullmatch(ports[0])
    if not match or int(match.group(1)) > 65535:
        raise ValueError("PROVISIONING-PORTA-NAO-LOCAL")
    return {
        "schema_version": 1,
        "service": "provisioning",
        "default_compose_starts_insecure_http": False,
        "bind_only_loopback": True,
        "profile": PROFILE,
        "profile_requires_explicit_opt_in": True,
        "http_lab_provisioning_secure": False,
        "tls_authentication_implemented_by_this_change": False,
        "real_yealink_tested": False,
        "production_go_authorized": False,
        "decision": "INSECURE_LAB_ONLY_DEFAULT_DENY",
    }


def inspect_file(path):
    file = Path(path)
    if file.is_symlink() or not file.is_file() or file.stat().st_size > MAX_COMPOSE_BYTES:
        raise ValueError("COMPOSE-ARQUIVO-INVALIDO")
    with file.open("r", encoding="utf-8") as stream:
        doc = yaml.safe_load(stream)
    return check_configuration(doc)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose", type=Path, default=ROOT / "docker-compose.yml")
    args = parser.parse_args(argv)
    try:
        report = inspect_file(args.compose)
    except (ValueError, TypeError, UnicodeError, OSError, yaml.YAMLError) as exc:
        print("PROVISIONING-NO-GO: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
