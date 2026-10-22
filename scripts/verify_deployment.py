#!/usr/bin/env python3
"""
Verificação pós-deploy (backlog #51) - roda DEPOIS que o
docker-compose está de pé num ambiente real. Complementa o roteiro
de implantação (manual 00) automatizando o que dá pra checar
programaticamente. NÃO substitui testar uma chamada de verdade -
cobre só "os serviços estão no ar" e "os segredos foram trocados",
não "o áudio funciona"/"a fila roteia certo".

NUNCA rodado contra um ambiente real neste projeto - só testado com
mocks (ver tests/test_deployment_checks.py e
tests/test_verify_deployment_runner.py). A primeira execução de
verdade é sua, ver docs/manual-51.

Uso:
    python3 scripts/verify_deployment.py
"""
import socket
import sys
from getpass import getpass
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from secrets_generator import find_placeholders  # noqa: E402
from deployment_checks import check_no_placeholder_secrets, parse_ami_login_result, summarize_http_health_checks  # noqa: E402

PROJECT_ROOT = Path(__file__).parent.parent

SECRET_FILES = [
    PROJECT_ROOT / "docker-compose.yml",
    PROJECT_ROOT / "asterisk" / "manager.conf",
    PROJECT_ROOT / "asterisk" / "pjsip.conf",
]

# host:porta pra cada serviço HTTP - ajuste se você mudou as portas
# padrão no docker-compose.yml
HTTP_SERVICES = {
    "queue-api": "http://127.0.0.1:8090/api/queue",
    "admin-api": "http://127.0.0.1:8091/",
    "ai-worker": "http://127.0.0.1:8092/api/transcripts",
    "webphone": "http://127.0.0.1:8082/",
}

AMI_HOST = "127.0.0.1"
AMI_PORT = 5038


def check_secrets() -> dict:
    contents = {}
    for path in SECRET_FILES:
        if path.exists():
            contents[str(path)] = path.read_text(encoding="utf-8")
    return check_no_placeholder_secrets(contents)


def check_ami_login(username: str, secret: str) -> bool:
    """Consulta login AMI: valida cabeçalhos e lê até o bloco terminar."""
    if not all(isinstance(value, str) and value and
               not any(ch in value for ch in "\\r\\n")
               for value in (username, secret)):
        return False
    try:
        with socket.create_connection((AMI_HOST, AMI_PORT), timeout=5) as sock:
            sock.settimeout(5)
            sock.recv(1024)  # banner de boas-vindas do Asterisk
            action = f"Action: Login\\r\\nUsername: {username}\\r\\nSecret: {secret}\\r\\n\\r\\n"
            sock.sendall(action.encode("utf-8"))
            payload = bytearray()
            for _ in range(8):  # máximo 8 blocos de recepção
                chunk = sock.recv(4096)
                if not chunk:
                    break
                payload.extend(chunk)
                if len(payload) > 16_384:
                    return False
                if b"\\r\\n\\r\\n" in payload:
                    return parse_ami_login_result(payload.decode("utf-8", errors="replace"))
            return False  # resposta incompleta ou conexão encerrada
    except (OSError, ValueError):
        return False


def check_http_services() -> dict:
    results = {}
    for name, url in HTTP_SERVICES.items():
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                results[name] = response.status
        except urllib.error.HTTPError as exc:
            results[name] = exc.code
        except Exception:  # noqa: BLE001
            results[name] = None
    return summarize_http_health_checks(results)


def main():
    print("=== Verificação pós-deploy ===\n")

    print("1. Segredos (nenhum placeholder deveria sobrar)...")
    secrets_result = check_secrets()
    if secrets_result["ok"]:
        print("   OK - nenhum placeholder 'troque_esta_senha_*' encontrado.\n")
    else:
        print("   FALHOU - ainda há placeholders. Rode scripts/generate_secrets.py primeiro:")
        for path, placeholders in secrets_result["remaining"].items():
            print(f"     {path}: {sorted(placeholders)}")
        print()

    print("2. AMI (login com AMI_USERNAME=queue-api)...")
    ami_ok = check_ami_login("queue-api", getpass("   AMI_SECRET do queue-api (entrada oculta): "))
    print("   OK - login aceito.\n" if ami_ok else "   FALHOU - login recusado ou Asterisk inacessível na porta 5038.\n")

    print("3. Serviços HTTP...")
    http_result = check_http_services()
    if http_result["all_healthy"]:
        print(f"   OK - todos saudáveis: {', '.join(http_result['healthy'])}\n")
    else:
        print(f"   FALHOU - {http_result['unhealthy']}\n")

    all_ok = secrets_result["ok"] and ami_ok and http_result["all_healthy"]
    print("=== RESULTADO: " + ("TUDO OK" if all_ok else "ENCONTRADOS PROBLEMAS ACIMA") + " ===")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
