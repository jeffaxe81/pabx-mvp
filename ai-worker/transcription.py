"""
Transcrição de áudio via Whisper local, usando whisper.cpp (via o
binding Python pywhispercpp) em vez de faster-whisper - motor em
C/C++ puro (ggml), mais leve pra hardware bem restrito (roda até em
Raspberry Pi com modelos pequenos), sem GPU. Mesmos pesos de modelo
Whisper (licença MIT) - a troca de motor não muda nada do lado
jurídico, só de onde/como roda.

O import da biblioteca é feito DENTRO da função, não no topo do
arquivo - assim o resto do módulo (validação de arquivo, etc.)
continua importável e testável mesmo num ambiente sem pywhispercpp
instalado (como o usado pra desenvolver/testar este projeto - ver
manual 36/47 pra essa limitação. NUNCA testado contra a biblioteca de
verdade neste ambiente - a assinatura exata da API pode variar por
versão do pywhispercpp; validar contra a lib real antes de produção).
"""
from pathlib import Path

SUPPORTED_EXTENSIONS = {".wav", ".gsm", ".mp3"}

_model_cache = {}


def is_supported_audio_file(path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def get_whisper_model(model_size: str = "base"):
    """
    Carrega (e cacheia) o modelo whisper.cpp do tamanho pedido -
    baixa automaticamente o arquivo .bin quantizado (ggml) na
    primeira execução, se ainda não existir localmente. Import
    tardio de propósito - ver docstring do módulo.
    """
    if model_size not in _model_cache:
        from pywhispercpp.model import Model  # noqa: PLC0415
        _model_cache[model_size] = Model(model_size, n_threads=4)
    return _model_cache[model_size]


def transcribe_audio(path, model_size: str = "base", language: str = "pt") -> str:
    """
    Transcreve um arquivo de áudio pra texto. Só a parte que
    realmente chama o whisper.cpp - a validação de arquivo é
    responsabilidade de quem chama (ver pipeline.py).
    """
    model = get_whisper_model(model_size)
    segments = model.transcribe(str(path), language=language)
    return " ".join(segment.text.strip() for segment in segments).strip()
