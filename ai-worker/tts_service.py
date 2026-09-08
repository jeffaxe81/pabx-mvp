"""
Síntese de voz (TTS, backlog #48) - camada de abstração entre motores,
mesmo padrão de llm_client.py isolando o Ollama do resto da lógica.

DECISÃO DE LICENCIAMENTO (importante, ver docs/manual-48):
- Piper (MIT) é o motor PADRÃO, sempre disponível - seguro pra uso
  comercial, consistente com o resto das escolhas de IA local deste
  projeto (Whisper/Llama também sem essa pegadinha).
- XTTS-v2 (Coqui) é OPCIONAL, DESLIGADO POR PADRÃO - a Coqui Public
  Model License PROÍBE uso comercial sem licença paga da Coqui, uma
  empresa que encerrou operações em 2024, sem caminho claro pra obter
  essa licença hoje. Só ative TTS_XTTS_ENABLED se seu uso for
  genuinamente não-comercial (avaliação, piloto, uso interno sem
  revenda) - e mesmo assim, confirme o estado atual da licença antes,
  isso muda com o tempo.

Lógica pura de validação/roteamento aqui - as chamadas de verdade aos
motores ficam isoladas em piper_engine.py/xtts_engine.py.
"""
import re

ENGINE_PIPER = "piper"
ENGINE_XTTS = "xtts"
VALID_ENGINES = {ENGINE_PIPER, ENGINE_XTTS}

SUPPORTED_LANGUAGES = {"pt", "en", "es"}
MAX_TEXT_LENGTH = 1000  # texto de anúncio de URA não deveria passar disso - limite defensivo

FILENAME_RE = re.compile(r"^[a-z0-9-]{3,60}$")


def validate_tts_request(data: dict, xtts_enabled: bool):
    """
    Retorna (ok, error_message, cleaned_data). xtts_enabled vem de
    fora (flag de configuração do servidor) - a validação não decide
    sozinha se XTTS está liberado, só recusa se pedirem XTTS com a
    flag desligada.
    """
    text = (data.get("text") or "").strip()
    if not text:
        return False, "texto obrigatório", None
    if len(text) > MAX_TEXT_LENGTH:
        return False, f"texto muito longo (máximo {MAX_TEXT_LENGTH} caracteres)", None

    language = (data.get("language") or "pt").strip()
    if language not in SUPPORTED_LANGUAGES:
        return False, f"idioma inválido - use um de: {sorted(SUPPORTED_LANGUAGES)}", None

    engine = (data.get("engine") or ENGINE_PIPER).strip()
    if engine not in VALID_ENGINES:
        return False, f"motor inválido - use um de: {sorted(VALID_ENGINES)}", None
    if engine == ENGINE_XTTS and not xtts_enabled:
        return False, "XTTS está desligado (uso não-comercial apenas - ver docs/manual-48 antes de ativar)", None

    raw_filename = (data.get("filename") or "").strip()
    if raw_filename:
        if not FILENAME_RE.match(raw_filename):
            return False, "nome de arquivo inválido (3-60 caracteres, letras minúsculas/números/hífen)", None
        filename = f"{raw_filename}.wav"
    else:
        filename = None  # server.py gera um nome aleatório se não for informado

    return True, None, {"text": text, "language": language, "engine": engine, "filename": filename}
