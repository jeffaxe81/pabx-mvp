"""
Testes dos placeholders de áudio da URA. Não valida conteúdo (são só
tons de beep, não uma gravação de verdade - ver manual 23) - só que
os arquivos existem e são WAV válidos no formato que o Asterisk espera.
"""
import wave
from pathlib import Path

SOUNDS_DIR = Path(__file__).parent.parent / "asterisk" / "sounds" / "custom"

EXPECTED_FILES = ["menu-principal.wav", "menu-fora-horario.wav", "menu-feriado.wav", "menu-callback.wav"]


def test_all_expected_placeholder_files_exist():
    missing = [f for f in EXPECTED_FILES if not (SOUNDS_DIR / f).is_file()]
    assert not missing, f"Placeholders de áudio ausentes: {missing}"


def test_placeholder_files_are_valid_mono_pcm_wav():
    for filename in EXPECTED_FILES:
        with wave.open(str(SOUNDS_DIR / filename), "rb") as wf:
            assert wf.getnchannels() == 1, f"{filename} deveria ser mono"
            assert wf.getsampwidth() == 2, f"{filename} deveria ser 16-bit"
            assert wf.getnframes() > 0, f"{filename} está vazio"
