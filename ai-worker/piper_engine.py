"""
Motor Piper (backlog #48) - motor PADRÃO de TTS, licença MIT, seguro
pra uso comercial. Import tardio, mesmo padrão do resto das
integrações de IA deste projeto (ver transcription.py/llm_client.py)
- assim o resto do módulo continua importável sem a lib instalada.

NUNCA testado contra a biblioteca de verdade neste ambiente - a
assinatura exata da API pode variar por versão do pacote `piper-tts`.
"""
from pathlib import Path

_voice_cache = {}

# Modelos de voz por idioma - nomes seguindo a convenção de modelo do
# projeto Piper (rhasspy/piper), baixados automaticamente na primeira
# execução se ainda não existirem localmente.
VOICE_MODELS = {
    "pt": "pt_BR-faber-medium",
    "en": "en_US-lessac-medium",
    "es": "es_ES-davefx-medium",
}


def get_voice(language: str):
    """Carrega (e cacheia) a voz Piper do idioma pedido."""
    if language not in _voice_cache:
        from piper import PiperVoice  # noqa: PLC0415
        model_name = VOICE_MODELS.get(language, VOICE_MODELS["pt"])
        _voice_cache[language] = PiperVoice.load(model_name)
    return _voice_cache[language]


def synthesize(text: str, language: str, output_path) -> None:
    """
    Gera o áudio e escreve em output_path (formato .wav, 8kHz mono -
    mesmo formato usado pelo resto dos áudios do projeto, ver
    manual 23). Não retorna nada - o arquivo é o resultado.
    """
    voice = get_voice(language)
    with open(Path(output_path), "wb") as audio_file:
        voice.synthesize(text, audio_file)
