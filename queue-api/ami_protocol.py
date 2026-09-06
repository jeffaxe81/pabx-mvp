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
    lines = [f"{key}: {value}" for key, value in fields.items()]
    return "\r\n".join(lines) + "\r\n\r\n"
