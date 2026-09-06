"""
server.py mistura HTTP real (não testável sem subir um servidor) com
decisões de segurança que valem a pena checar estaticamente - ex: "o
endpoint de click-to-call está mesmo protegido por validação antes de
tocar na AMI?". Esses testes leem o código-fonte, não executam o
servidor.
"""
from pathlib import Path

SERVER_PY = Path(__file__).parent.parent / "server.py"


def load_source():
    return SERVER_PY.read_text(encoding="utf-8")


def test_click_to_call_route_is_registered():
    source = load_source()
    assert '"/api/click-to-call"' in source
    assert "_handle_click_to_call" in source


def test_click_to_call_disabled_by_default():
    source = load_source()
    assert 'os.environ.get("CLICK_TO_CALL_API_KEY", "")' in source


def test_click_to_call_validates_before_touching_ami():
    """
    A validação (chave de API, ramal permitido, número sanitizado)
    precisa acontecer ANTES de qualquer chamada à AMI - senão a
    proteção não protege nada.
    """
    source = load_source()
    fn_start = source.index("def _handle_click_to_call")
    fn_end = source.index("\n\n", source.index("falha ao originar chamada", fn_start))
    body = source[fn_start:fn_end]

    validate_pos = body.index("validate_click_to_call_request(")
    ami_pos = body.index("ami.send_action(")
    assert validate_pos < ami_pos


def test_click_to_call_checks_ami_connected():
    source = load_source()
    fn_start = source.index("def _handle_click_to_call")
    fn_end = source.index("\n\n", source.index("falha ao originar chamada", fn_start))
    body = source[fn_start:fn_end]
    assert "if ami is None:" in body
