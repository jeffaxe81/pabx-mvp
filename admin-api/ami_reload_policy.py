"""Validação conservadora da saída CLI retornada pelo AMI Command.

Response: Follows significa que a saída textual do comando foi
encaminhada; não garante que o CLI do Asterisk aceitou o comando.
"""
import re


_NEGATIVE_CLI_PATTERNS = (
    re.compile(r"^\s*No such command\b", re.I),
    re.compile(r"^\s*Unknown command\b", re.I),
    re.compile(r"^\s*Command\s+.+\s+(?:failed|not found)\b", re.I),
    re.compile(r"^\s*Failed to (?:reload|load)\b", re.I),
    re.compile(r"^\s*Unable to (?:reload|load)\b", re.I),
    re.compile(r"^\s*Error (?:loading|reloading)\b", re.I),
    re.compile(r"^\s*Error executing command\b", re.I),
    re.compile(r"^\s*Module\s+.+\s+reload failed\b", re.I),
)


def cli_reload_output_failed(output: str) -> bool:
    """Encontra erros explícitos sem reprovar mensagens informativas.

    Não usa um match genérico de 'error': mensagens como '0 errors'
    podem fazer parte da resposta de um reload válido.
    """
    if not isinstance(output, str):
        return True
    return any(
        pattern.search(line)
        for line in output.splitlines()
        for pattern in _NEGATIVE_CLI_PATTERNS
    )
