"""
AGI (Asterisk Gateway Interface) é o protocolo simples baseado em
texto que o Asterisk usa pra rodar um script externo no meio do
dialplan: manda o ambiente da chamada por stdin, o script manda
comandos por stdout, o Asterisk responde por stdin.

Esse módulo tem só a parte de PARSING e MONTAGEM de comandos (lógica
pura, testável sem precisar de um processo Asterisk de verdade
conversando via stdin/stdout). A leitura/escrita de verdade fica no
script principal (atendente_virtual.py) - ver manual 37.
"""


def parse_agi_env(lines: list) -> dict:
    """
    Parseia as linhas de ambiente que o Asterisk manda no início
    (formato 'agi_chave: valor'), até a linha em branco que marca o
    fim do bloco (essa linha em branco não deve estar em `lines`).
    """
    env = {}
    for line in lines:
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        env[key.strip()] = value.strip()
    return env


def build_record_command(filename: str, audio_format: str = "wav", escape_digits: str = "#", timeout_ms: int = 8000, silence_seconds: int = 2) -> str:
    """
    Monta o comando AGI 'RECORD FILE' - grava a fala do cliente até
    detectar silêncio (ou o dígito de escape, ou o timeout). Sem
    escape_digits, o cliente não teria como sinalizar "terminei de
    falar" antes do timeout.
    """
    return f'RECORD FILE "{filename}" {audio_format} "{escape_digits}" {timeout_ms} 0 BEEP s={silence_seconds}'


def build_set_variable_command(name: str, value: str) -> str:
    """Monta o comando AGI que define uma variável de canal, lida depois pelo dialplan."""
    return f'SET VARIABLE {name} "{value}"'


def build_stream_file_command(filename: str, escape_digits: str = "") -> str:
    """
    Monta o comando AGI 'STREAM FILE' - toca um áudio pro cliente
    (backlog #48, fase 2: confirmação falada do atendente virtual).
    filename é relativo à pasta de sons do Asterisk, sem extensão
    (ex: "custom/tts-abc123", não "custom/tts-abc123.wav") - mesma
    convenção usada por Playback()/Background() no dialplan.
    """
    return f'STREAM FILE "{filename}" "{escape_digits}"'


def parse_agi_response(line: str) -> dict:
    """
    Parseia a resposta do Asterisk a um comando AGI - formato típico
    '200 result=1 (timeout)' ou '200 result=0'. Retorna
    {"code": int, "result": str, "raw": str}. Nunca lança exceção -
    uma resposta em formato inesperado não pode derrubar o script.
    """
    line = line.strip()
    parts = line.split(" ", 1)
    try:
        code = int(parts[0])
    except (ValueError, IndexError):
        return {"code": None, "result": None, "raw": line}

    result = None
    if len(parts) > 1 and "result=" in parts[1]:
        after = parts[1].split("result=", 1)[1]
        result = after.split(" ", 1)[0].split("(", 1)[0].strip()

    return {"code": code, "result": result, "raw": line}
