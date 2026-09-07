"""
Atendente virtual com IA (backlog #24) - implementado como uma
PRIMEIRA CAMADA DE TRIAGEM, não como um robô conversacional completo:
o cliente descreve em poucas palavras o motivo da ligação, o Whisper
transcreve, o Llama 3 classifica a intenção (vendas/suporte/outro), e
o dialplan roteia pro destino certo automaticamente. Ver manual 37
pra essa distinção de escopo - um bot de voz bidirecional em tempo
real (perguntas e respostas faladas) é um projeto bem maior, fora do
que foi construído aqui.

Prompt e parsing são puros - a chamada de rede fica em llm_client.py.
"""

VALID_INTENTS = {"vendas", "suporte", "outro"}

# Mapeia a intenção classificada pro destino no dialplan (mesmos
# pontos já usados pela URA manual, manual 23)
INTENT_TO_EXTENSION = {
    "vendas": "1000",
    "suporte": "1010",
    "outro": "1000",  # sem certeza -> cai na fila geral, não descarta a ligação
}


def build_intent_prompt(transcript: str) -> str:
    return (
        "Um cliente ligou pra uma central de atendimento e descreveu o "
        "motivo da ligação. Classifique a intenção dele em UMA PALAVRA, "
        "exatamente uma destas: vendas, suporte ou outro. "
        "Use 'vendas' pra interesse em comprar/contratar algo novo. "
        "Use 'suporte' pra problema com algo que o cliente já tem/já "
        "contratou. Use 'outro' se não for nenhum dos dois ou não ficar "
        "claro. Responda só a palavra, nada mais.\n\n"
        f"O que o cliente disse: \"{transcript}\"\n\nIntenção:"
    )


def parse_intent_response(raw_response: str) -> str:
    """
    Mesmo padrão de tolerância do sentiment.py - procura a palavra
    válida em vez de exigir correspondência exata. 'outro' é o
    fallback seguro (cai na fila geral, não perde a ligação) tanto
    pra quando o modelo genuinamente classifica como 'outro' quanto
    pra quando a resposta vem em formato inesperado.
    """
    normalized = raw_response.strip().lower()
    for intent in ("vendas", "suporte"):  # checa os específicos antes do fallback
        if intent in normalized:
            return intent
    return "outro"


def intent_to_extension(intent: str) -> str:
    """Sempre retorna um destino válido - nunca None, mesmo pra intenção desconhecida."""
    return INTENT_TO_EXTENSION.get(intent, INTENT_TO_EXTENSION["outro"])
