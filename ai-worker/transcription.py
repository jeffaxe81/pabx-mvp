"""
Transcrição de áudio via Whisper local, usando a biblioteca
faster-whisper (CTranslate2 - roda em CPU, mais leve que o Whisper
original em PyTorch puro).

O import da biblioteca é feito DENTRO da função, não no topo do
arquivo - assim o resto do módulo (validação de arquivo, etc.)
continua importável e testável mesmo num ambiente sem faster-whisper
instalado (como o usado pra desenvolver/testar este projeto - ver
manual 36 pra essa limitação).
"""
from pathlib import Path

SUPPORTED_EXTENSIONS = {".wav", ".gsm", ".mp3"}

_model_cache = {}


def is_supported_audio_file(path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def get_whisper_model(model_size: str = "base"):
    """
    Carrega (e cacheia) o modelo Whisper do tamanho pedido. Import
    tardio de propósito - ver docstring do módulo.
    """
    if model_size not in _model_cache:
        from faster_whisper import WhisperModel  # noqa: PLC0415
        _model_cache[model_size] = WhisperModel(model_size, device="cpu", compute_type="int8")
    return _model_cache[model_size]


def transcribe_audio(path, model_size: str = "base", language: str = "pt") -> str:
    """
    Transcreve um arquivo de áudio pra texto. Só a parte que
    realmente chama o Whisper - a validação de arquivo é
    responsabilidade de quem chama (ver pipeline.py).
    """
    model = get_whisper_model(model_size)
    segments, _info = model.transcribe(str(path), language=language)
    return " ".join(segment.text.strip() for segment in segments).strip()
