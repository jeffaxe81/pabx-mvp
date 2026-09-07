"""
Análise de sentimento de chamada (backlog #23), a partir da
transcrição, via LLM local. Mesmo padrão de summarizer.py: prompt e
parsing são puros, a chamada de rede fica em llm_client.py.
"""

VALID_SENTIMENTS = {"positivo", "neutro", "negativo"}


def build_sentiment_prompt(transcript: str) -> str:
    return (
        "Classifique o sentimento predominante do cliente na transcrição de "
        "atendimento abaixo. Responda com APENAS UMA PALAVRA, exatamente uma "
        "destas: positivo, neutro ou negativo. Não escreva mais nada além "
        "dessa palavra.\n\n"
        f"Transcrição:\n{transcript}\n\nSentimento:"
    )


def parse_sentiment_response(raw_response: str) -> str:
    """
    Extrai o sentimento da resposta do modelo. Modelos nem sempre
    obedecem "responda só uma palavra" - por isso procura a primeira
    palavra válida em vez de exigir correspondência exata. Retorna
    'indefinido' se não encontrar nenhuma das três palavras esperadas -
    isso é honesto: o modelo pode ter "alucinado" ou fugido do
    formato, e fingir uma classificação seria pior que admitir que não
    deu pra classificar.
    """
    normalized = raw_response.strip().lower()
    for sentiment in VALID_SENTIMENTS:
        if sentiment in normalized:
            return sentiment
    return "indefinido"