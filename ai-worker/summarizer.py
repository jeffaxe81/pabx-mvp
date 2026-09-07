"""
Resumo automático de chamada (backlog #22), a partir da transcrição
(transcription.py) via LLM local (llm_client.py). Montagem de prompt
e validação da resposta são lógica pura - a chamada de rede de
verdade fica isolada em llm_client.generate().
"""

MIN_TRANSCRIPT_LENGTH = 20  # abaixo disso, não vale a pena gastar chamada de LLM


def build_summary_prompt(transcript: str) -> str:
    return (
        "Você é um assistente que resume ligações de atendimento ao cliente.\n"
        "Resuma a transcrição abaixo em no máximo 3 frases curtas, em português, "
        "destacando o motivo do contato e o que foi combinado ou resolvido.\n"
        "Não invente informação que não está na transcrição.\n\n"
        f"Transcrição:\n{transcript}\n\nResumo:"
    )


def is_transcript_worth_summarizing(transcript: str) -> bool:
    """
    Transcrição vazia ou curta demais (ex: chamada que caiu em 2s, ou
    Whisper não reconheceu nada) não vale a pena mandar pro LLM -
    economiza uma chamada cara e evita um "resumo" de nada.
    """
    return bool(transcript and len(transcript.strip()) >= MIN_TRANSCRIPT_LENGTH)


def clean_summary_response(raw_response: str) -> str:
    """
    Remove prefixos comuns que modelos às vezes adicionam ("Resumo:",
    aspas, etc.) - não é infalível, mas cobre os casos mais comuns
    sem precisar de outra chamada de LLM só pra limpar a primeira.
    """
    cleaned = raw_response.strip()
    for prefix in ("Resumo:", "resumo:", "Resumo -", "**Resumo:**"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    return cleaned.strip('"').strip()
