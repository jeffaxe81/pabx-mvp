"""
Funções puras de parsing/montagem do protocolo AMI (Asterisk Manager
Interface). Nenhuma função aqui abre socket - isso é de propósito,
pra dar pra testar 100% sem precisar de um Asterisk de verdade rodando.

Protocolo AMI é simples: blocos de texto "Chave: Valor" separados por
"\r\n", e um bloco termina com uma linha em branco.
"""


def parse_ami_blocks(raw_text: str):
    """
    Recebe um texto cru (pode conter vários blocos, ex: várias
    respostas/eventos recebidos de uma vez do socket) e retorna uma
    lista de dicts, um por bloco.
    """
    raw_text = raw_text.replace("\r\n", "\n")
    blocks_text = raw_text.split("\n\n")

    blocks = []
    for block_text in blocks_text:
        block_text = block_text.strip("\n")
        if not block_text:
            continue

        block = {}
        for line in block_text.split("\n"):
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            block[key.strip()] = value.strip()

        if block:
            blocks.append(block)

    return blocks


def build_action(fields: dict) -> str:
    """
    Monta uma Action AMI a partir de um dict, na ordem em que as
    chaves foram inseridas (Python 3.7+ preserva ordem de dict).
    Ex: build_action({"Action": "Login", "Username": "x"})
    """
    if not isinstance(fields, dict) or not fields:
        raise ValueError("Ação AMI vazia ou inválida")
    lines = []
    for key, value in fields.items():
        if (not isinstance(key, str) or not 1 <= len(key) <= 64
                or any(ord(c) < 33 or ord(c) > 126 or c == ':' for c in key)):
            raise ValueError("Campo AMI inválido")
        value = str(value)
        if "\r" in value or "\n" in value:
            raise ValueError("Quebra de linha proibida em campo AMI")
        lines.append(f"{key}: {value}")
    return "\r\n".join(lines) + "\r\n\r\n"
