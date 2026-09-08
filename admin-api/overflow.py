"""
Timeout de overflow entre filas configurável por tenant (backlog #56)
- fecha a limitação documentada no manual 45 ("sem interface no
painel pra ajustar o valor"). Guardado no AstDB (família
"config-{tenant}", mesma família do modo feriado - manual 23), chave
"overflow-timeout-segundos".

Lógica pura de validação aqui - a leitura/escrita de verdade fica
isolada em ami_client.py/server.py, mesmo padrão do resto do projeto.
"""

MIN_SECONDS = 5   # abaixo disso não dá tempo nem de tocar
MAX_SECONDS = 600  # acima de 10 minutos não é mais "overflow", é só uma fila comum


def validate_overflow_timeout_input(data: dict):
    """Retorna (ok, error_message, cleaned_seconds)."""
    raw = data.get("seconds")
    try:
        seconds = int(raw)
    except (TypeError, ValueError):
        return False, "tempo de overflow deve ser um número inteiro de segundos", None

    if not (MIN_SECONDS <= seconds <= MAX_SECONDS):
        return False, f"tempo de overflow deve estar entre {MIN_SECONDS} e {MAX_SECONDS} segundos", None

    return True, None, seconds
