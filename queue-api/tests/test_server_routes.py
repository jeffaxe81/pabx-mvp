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


def test_campaigns_reuse_click_to_call_api_key_protection():
    """
    Campanhas originam chamada via AMI, mesma categoria de risco do
    click-to-call - por isso precisam da mesma checagem de chave,
    ANTES de qualquer criação/disparo.
    """
    source = load_source()
    for fn_name in ("_handle_list_campaigns", "_handle_get_campaign", "_handle_create_campaign", "_handle_dial_next_contact"):
        fn_start = source.index(f"def {fn_name}")
        fn_end = source.index("\n    def ", fn_start + 10)
        body = source[fn_start:fn_end]
        assert "_require_campaign_api_key()" in body, f"{fn_name} sem checagem de chave"


def test_dial_next_contact_marks_calling_before_originating():
    """
    O contato precisa ser marcado como 'discando' ANTES do Originate
    de verdade - senão uma corrida entre dois cliques de 'discar
    próximo' poderia tentar ligar pro mesmo contato duas vezes.
    """
    source = load_source()
    fn_start = source.index("def _handle_dial_next_contact")
    fn_end = source.index("\n    def ", fn_start + 10)
    body = source[fn_start:fn_end]
    mark_pos = body.index("mark_contact_calling(")
    originate_pos = body.index("ami.send_action(action)")
    assert mark_pos < originate_pos


def test_callback_routes_reuse_same_api_key_protection():
    source = load_source()
    for fn_name in ("_handle_list_callbacks", "_handle_dial_next_callback"):
        fn_start = source.index(f"def {fn_name}")
        fn_end = source.index("\n    def ", fn_start + 10)
        body = source[fn_start:fn_end]
        assert "_require_campaign_api_key()" in body, f"{fn_name} sem checagem de chave"


def test_callback_dial_marks_calling_before_originating():
    source = load_source()
    fn_start = source.index("def _handle_dial_next_callback")
    fn_end = source.index("\n    def ", fn_start + 10)
    body = source[fn_start:fn_end]
    mark_pos = body.index("mark_callback_calling(")
    originate_pos = body.index("ami.send_action(action)")
    assert mark_pos < originate_pos


def test_extension_states_endpoint_merges_manual_presence():
    """
    Sem essa mesclagem, o painel operacional continuaria mostrando só
    livre/tocando/ocupado - a presença manual (ausente/reunião/
    férias) simplesmente nunca apareceria em lugar nenhum.
    """
    source = load_source()
    fn_start = source.index('"/api/extension-states"')
    fn_end = source.index("elif", fn_start)
    body = source[fn_start:fn_end]
    assert "merge_presence_into_states(" in body


def test_presence_validates_before_persisting():
    source = load_source()
    fn_start = source.index("def _handle_set_presence")
    signature_end = source.index("):", fn_start) + 2
    fn_end = source.index("\n    def ", signature_end)
    body = source[signature_end:fn_end]
    validate_pos = body.index("validate_presence_input(")
    set_pos = body.index("set_presence(")
    assert validate_pos < set_pos


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
