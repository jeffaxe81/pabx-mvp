"""
Verificação estática do server.py - mesmo padrão já usado no resto
do projeto (queue-api/tests/test_server_routes.py etc.).
"""
from pathlib import Path

SERVER_PY = Path(__file__).parent.parent / "server.py"


def load_source():
    return SERVER_PY.read_text(encoding="utf-8")


def test_ai_features_disabled_by_default():
    source = load_source()
    assert 'os.environ.get("AI_FEATURES_ENABLED", "false")' in source


def test_scan_loop_checks_flag_before_processing():
    source = load_source()
    fn_start = source.index("def scan_loop")
    fn_end = source.index("\n\nclass Handler", fn_start)
    body = source[fn_start:fn_end]
    flag_pos = body.index("AI_FEATURES_ENABLED")
    process_pos = body.index("process_next_pending()")
    assert flag_pos < process_pos


def test_manual_process_endpoint_checks_flag_before_processing():
    """
    Mesmo o disparo manual (POST /api/process/<arquivo>) não pode
    rodar se AI_FEATURES_ENABLED estiver desligado - senão a flag
    "desligado por padrão" não protege nada de verdade.
    """
    source = load_source()
    fn_start = source.index("def do_POST")
    fn_end = source.index("\n\ndef main", fn_start)
    body = source[fn_start:fn_end]
    flag_check_pos = body.index("if not AI_FEATURES_ENABLED:")
    process_call_pos = body.index("process_recording(")
    assert flag_check_pos < process_call_pos


def test_classify_intent_checks_flag_before_transcribing():
    source = load_source()
    fn_start = source.index("def _handle_classify_intent")
    fn_end = source.index("\n\nclass ", fn_start) if "\n\nclass " in source[fn_start:] else len(source)
    body = source[fn_start:fn_end]
    flag_pos = body.index("if not AI_FEATURES_ENABLED:")
    transcribe_pos = body.index("transcribe_audio(")
    assert flag_pos < transcribe_pos


def test_classify_intent_always_returns_a_valid_extension():
    """
    Mesmo sem transcrição (gravação vazia/curta demais), o endpoint
    precisa devolver um destino válido - nunca travar a chamada sem
    resposta nenhuma.
    """
    source = load_source()
    fn_start = source.index("def _handle_classify_intent")
    fn_end = source.index("\n\nclass ", fn_start) if "\n\nclass " in source[fn_start:] else len(source)
    body = source[fn_start:fn_end]
    assert 'intent_to_extension("outro")' in body


def test_scan_loop_processes_one_recording_at_a_time():
    """
    Sem paralelismo de propósito - Whisper/Llama em CPU já competem
    por recursos sozinhos, processar várias gravações ao mesmo tempo
    deixaria tudo mais lento, não mais rápido.
    """
    source = load_source()
    fn_start = source.index("def process_next_pending")
    fn_end = source.index("\n\ndef scan_loop", fn_start)
    body = source[fn_start:fn_end]
    assert "pending[0]" in body
