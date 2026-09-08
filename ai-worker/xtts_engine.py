"""
Motor XTTS-v2 / Coqui (backlog #48) - OPCIONAL, DESLIGADO POR PADRÃO.

AVISO DE LICENCIAMENTO (leia antes de ativar): o modelo XTTS-v2 é
distribuído sob a Coqui Public Model License (CPML), que PROÍBE uso
comercial sem uma licença paga da Coqui. A empresa Coqui.ai encerrou
operações em 2024 - não há hoje um caminho claro pra obter essa
licença comercial, mesmo que alguém queira pagar por ela. Só use este
motor se seu uso for genuinamente não-comercial (avaliação, piloto,
uso interno sem revenda) - e confirme o estado atual da licença antes
de decidir, isso é uma área que muda com o tempo. Ver docs/manual-48.

Import tardio, mesmo padrão do resto do projeto - nunca testado
contra a biblioteca de verdade neste ambiente.
"""
from pathlib import Path

_model_cache = {}

XTTS_MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"


def get_xtts_model():
    """Carrega (e cacheia) o modelo XTTS-v2 - pesado, carregar uma vez só."""
    if "model" not in _model_cache:
        from TTS.api import TTS  # noqa: PLC0415
        _model_cache["model"] = TTS(XTTS_MODEL_NAME)
    return _model_cache["model"]


def synthesize(text: str, language: str, output_path, speaker_wav: str = None) -> None:
    """
    Gera o áudio e escreve em output_path. speaker_wav é opcional -
    se informado, tenta clonar a voz da amostra fornecida (recurso
    característico do XTTS); sem isso, usa uma voz padrão do modelo.
    """
    model = get_xtts_model()
    model.tts_to_file(
        text=text,
        language=language,
        file_path=str(Path(output_path)),
        speaker_wav=speaker_wav,
    )
