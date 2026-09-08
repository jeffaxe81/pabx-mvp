"""
Checagens de verificação pós-deploy (backlog #51) - complementa o
roteiro de implantação (manual 00) com automação do que dá pra
verificar programaticamente. NÃO substitui testar numa chamada de
verdade - cobre só o que é mecanicamente checável (serviço no ar,
credencial não é mais placeholder, endpoint responde).

Lógica pura de parsing/decisão aqui - as chamadas de rede de verdade
(AMI, HTTP) ficam isoladas em verify_deployment.py, mesmo padrão do
resto do projeto. Nunca testado contra um deploy real - só com mocks.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from secrets_generator import find_placeholders  # noqa: E402


def check_no_placeholder_secrets(file_contents: dict) -> dict:
    """
    Recebe {caminho: conteúdo} de cada arquivo que pode ter
    placeholder, devolve {"ok": bool, "remaining": {caminho: {placeholders}}}
    - só os arquivos com placeholder sobrando aparecem no resultado,
    pra não poluir um relatório de "tudo certo" com entradas vazias.
    """
    remaining = {}
    for path, content in file_contents.items():
        found = find_placeholders(content)
        if found:
            remaining[path] = found
    return {"ok": not remaining, "remaining": remaining}


def parse_ami_login_result(response_text: str) -> bool:
    """
    A resposta de login AMI bem-sucedida começa com 'Response:
    Success' - qualquer outra coisa (erro de autenticação, timeout,
    resposta vazia) conta como falha.
    """
    return response_text.strip().startswith("Response: Success")


def summarize_http_health_checks(results: dict) -> dict:
    """
    Recebe {nome_do_serviço: status_code_ou_None} (None = não
    respondeu/erro de rede), devolve um resumo com quem está saudável
    e quem não está - 200 é o único código considerado saudável aqui
    (os serviços deste projeto não usam outros 2xx).
    """
    healthy = {name: code for name, code in results.items() if code == 200}
    unhealthy = {name: code for name, code in results.items() if code != 200}
    return {
        "all_healthy": not unhealthy,
        "healthy": sorted(healthy),
        "unhealthy": unhealthy,
    }
