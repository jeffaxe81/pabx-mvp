"""
Cliente do Ollama (https://ollama.com) - servidor que roda o Llama 3
localmente e expõe uma API HTTP simples. Usado pelo resumo automático
(manual 36), análise de sentimento (manual 36) e classificação de
intenção do atendente virtual (manual 37).

Separação de propósito: montagem da requisição e parsing da resposta
são funções PURAS (testáveis sem rede); o envio de verdade
(`generate`) é a parte que só dá pra validar contra um Ollama real
rodando - mesma situação já documentada pro resto das integrações de
rede deste projeto (AMI, SMTP, webhooks).
"""
import json
import urllib.request
from urllib.parse import urlsplit


def build_generate_request(prompt: str, model: str = "llama3", temperature: float = 0.2) -> dict:
    """
    Monta o corpo da requisição pro endpoint /api/generate do Ollama.
    Temperatura baixa de propósito - resumo/sentimento/classificação
    devem ser consistentes, não criativos.
    """
    return {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }


def extract_response_text(ollama_response: dict) -> str:
    """
    Extrai o texto gerado da resposta do Ollama. Retorna string vazia
    (não lança exceção) se o formato vier inesperado - uma falha aqui
    não pode derrubar o resto do pipeline de processamento.
    """
    if not isinstance(ollama_response, dict):
        return ""
    value = ollama_response.get("response")
    return value.strip() if isinstance(value, str) else ""


def generate(base_url: str, prompt: str, model: str = "llama3", timeout: int = 120) -> str:
    """
    Chamada de rede de verdade pro Ollama. `timeout` alto de propósito
    - modelos locais em CPU podem demorar bem mais que uma API na nuvem.
    """
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("URL do Ollama inválida: use HTTP(S) sem credenciais embutidas")
    request_body = build_generate_request(prompt, model)
    data = json.dumps(request_body).encode("utf-8")

    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/generate",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        # Respostas descontroladas não podem consumir memória ilimitada.
        payload = response.read(2_000_001)
        if len(payload) > 2_000_000:
            raise ValueError("Resposta do Ollama excedeu limite de 2 MB")
        body = json.loads(payload.decode("utf-8"))
        return extract_response_text(body)
