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
    if not isinstance(response_text, str):
        return False
    # A primeira linha Response decide o login, evitando falso positivo
    # com valores como "SuccessExtra" ou resposta posterior divergente.
    for line in response_text.splitlines():
        value = line.strip()
        if value.startswith("Response:"):
            return value == "Response: Success"
    return False


def summarize_http_health_checks(results: dict, required_codes=None) -> dict:
    """
    Retorna saúde por resposta EXATA esperada em cada rota. O default 200
    preserva consumidores antigos; o verificador pós-deploy passa
    explicitamente 401 para a API de filas protegida por Bearer.
    401 aqui só prova que a barreira HTTP responde, não valida um login.
    """
    expected = required_codes or {}
    healthy = {name: code for name, code in results.items()
               if type(code) is int and code == expected.get(name, 200)}
    unhealthy = {name: code for name, code in results.items()
                 if name not in healthy}
    return {
        "all_healthy": not unhealthy,
        "healthy": sorted(healthy),
        "unhealthy": unhealthy,
    }
