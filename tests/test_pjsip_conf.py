"""
Testes estáticos do asterisk/pjsip.conf.

Não sobem o Asterisk de verdade (isso é o próximo nível, com testes de
integração via container) - validam que a estrutura de configuração
está consistente: transportes, endpoints esperados por tenant, e que
endpoints seguros/webrtc usam criptografia de fato (inclusive quando a
chave só existe herdada de um template).
"""
from pathlib import Path

from conf_parser import parse_blocks, get_key, get_key_inherited, blocks_by_type

PJSIP_CONF = Path(__file__).parent.parent / "asterisk" / "pjsip.conf"
EXTENSIONS_CONF = Path(__file__).parent.parent / "asterisk" / "extensions.conf"


def load_blocks():
    return parse_blocks(PJSIP_CONF)


def test_transports_exist():
    blocks = load_blocks()
    transport_names = {b["name"] for b in blocks_by_type(blocks, "transport")}
    assert "transport-udp" in transport_names
    assert "transport-tls" in transport_names
    assert "transport-wss" in transport_names


def test_tls_transport_has_certificates():
    blocks = load_blocks()
    tls_blocks = [b for b in blocks_by_type(blocks, "transport") if b["name"] == "transport-tls"]
    assert tls_blocks, "transport-tls não encontrado"
    block = tls_blocks[0]
    assert get_key(block["text"], "cert_file")
    assert get_key(block["text"], "priv_key_file")


def test_expected_endpoints_present():
    blocks = load_blocks()
    endpoint_names = {b["name"] for b in blocks_by_type(blocks, "endpoint")}
    expected = {
        "t1-1001", "t1-1002", "t1-recepcao", "t1-recepcao-2",
        "t2-1001", "t2-recepcao", "t2-recepcao-2",
        "gateway-tdm", "gateway-tdm-2",
    }
    missing = expected - endpoint_names
    assert not missing, f"Endpoints esperados ausentes: {missing}"


def test_tenant2_telephonist_endpoints_use_webrtc_template():
    """
    Backlog #38 (multi-tenant completo): as telefonistas web do
    tenant 2 precisam existir com a mesma configuração WebRTC das do
    tenant 1 - senão o console da telefonista não funcionaria pra
    ninguém do tenant 2.
    """
    blocks = load_blocks()
    endpoints = {b["name"]: b for b in blocks_by_type(blocks, "endpoint")}
    for name in ("t2-recepcao", "t2-recepcao-2"):
        block = endpoints[name]
        assert get_key(block["text"], "context") == "t2-internal"
        assert get_key_inherited(block, "webrtc", blocks) == "yes"


def test_every_endpoint_has_matching_auth_and_aor():
    """
    Todo ramal (exceto o tronco identificado por IP) deve ter um bloco
    auth e um bloco aor com o mesmo nome - senão o Asterisk não sobe o
    ramal corretamente. Templates puros (endpoint-base, etc.) são
    ignorados: eles nunca registram sozinhos.
    """
    blocks = load_blocks()
    template_names = {"endpoint-base", "endpoint-plain", "endpoint-secure", "endpoint-webrtc"}

    endpoint_names = {b["name"] for b in blocks_by_type(blocks, "endpoint")} - template_names
    auth_names = {b["name"] for b in blocks_by_type(blocks, "auth")}
    aor_names = {b["name"] for b in blocks_by_type(blocks, "aor")}

    # troncos identificados por IP não usam auth de usuário/senha
    endpoints_needing_auth = endpoint_names - {"gateway-tdm", "gateway-tdm-2"}

    missing_auth = endpoints_needing_auth - auth_names
    missing_aor = endpoint_names - aor_names

    assert not missing_auth, f"Ramais sem bloco auth: {missing_auth}"
    assert not missing_aor, f"Ramais sem bloco aor: {missing_aor}"


def test_web_endpoint_uses_webrtc_and_wss():
    blocks = load_blocks()
    endpoints = {b["name"]: b for b in blocks_by_type(blocks, "endpoint")}
    for name in ("t1-recepcao", "t1-recepcao-2"):
        assert name in endpoints
        block = endpoints[name]
        assert get_key_inherited(block, "webrtc", blocks) == "yes", (
            f"{name} deveria resultar em webrtc=yes (direto ou herdado de template)"
        )
        assert get_key_inherited(block, "transport", blocks) == "transport-wss"


def test_secure_endpoints_use_encryption():
    """
    Os ramais internos (não-web) devem herdar media_encryption do
    template endpoint-secure - garante que ninguém trocou por engano
    para o template sem criptografia (endpoint-plain).
    """
    blocks = load_blocks()
    endpoints = {b["name"]: b for b in blocks_by_type(blocks, "endpoint")}
    for name in ("t1-1001", "t1-1002", "t2-1001"):
        block = endpoints[name]
        encryption = get_key_inherited(block, "media_encryption", blocks)
        assert encryption in ("sdes", "dtls"), (
            f"Ramal {name} sem criptografia de mídia (media_encryption={encryption})"
        )


def test_no_weak_or_placeholder_passwords():
    """
    Sanity check: garante que ninguém trocou por engano os placeholders
    de senha por strings vazias ou óbvias como '123456'.
    """
    blocks = load_blocks()
    for block in blocks_by_type(blocks, "auth"):
        password = get_key(block["text"], "password")
        assert password, f"auth {block['name']} sem senha definida"
        assert password not in {"", "123456", "senha", "admin"}, (
            f"auth {block['name']} com senha fraca demais: {password}"
        )


def test_subscribe_context_points_to_existing_hint_context():
    """
    Cada endpoint com subscribe_context (direto ou herdado) deve
    apontar para um contexto que realmente existe em extensions.conf -
    senão o BLF na interface web fica quebrado silenciosamente.
    """
    ext_blocks = parse_blocks(EXTENSIONS_CONF)
    existing_contexts = {b["name"] for b in ext_blocks}

    blocks = load_blocks()
    for block in blocks_by_type(blocks, "endpoint"):
        subscribe_context = get_key_inherited(block, "subscribe_context", blocks)
        if subscribe_context:
            assert subscribe_context in existing_contexts, (
                f"Endpoint {block['name']} referencia subscribe_context inexistente: {subscribe_context}"
            )


def test_pjsip_conf_includes_admin_panel_dynamic_extensions():
    """
    Sem esse #include, ramais criados pelo painel de administração
    (backlog #10) nunca aparecem no PJSIP de verdade.
    """
    content = PJSIP_CONF.read_text(encoding="utf-8")
    assert "#include pjsip_dynamic.conf" in content


def test_pjsip_includes_wizard_created_tenants_via_wildcard():
    """Backlog #39: tenant novo criado pelo wizard aparece automaticamente, sem editar este arquivo."""
    content = PJSIP_CONF.read_text(encoding="utf-8")
    assert "#include pjsip_tenants/*.conf" in content
