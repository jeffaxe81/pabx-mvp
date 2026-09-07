"""
Testes estáticos do asterisk/extensions.conf.
"""
import re
from pathlib import Path

from conf_parser import parse_blocks, blocks_by_type

EXTENSIONS_CONF = Path(__file__).parent.parent / "asterisk" / "extensions.conf"
PJSIP_CONF = Path(__file__).parent.parent / "asterisk" / "pjsip.conf"

HINT_RE = re.compile(r"exten\s*=>\s*(\S+),hint,(\S+)")


def load_ext_blocks():
    return parse_blocks(EXTENSIONS_CONF)


def blocks_as_dict(blocks):
    """
    extensions.conf não usa herança de template como o pjsip.conf, mas
    o mesmo nome de contexto nunca deveria se repetir aqui - então um
    dict simples é seguro.
    """
    return {b["name"]: b["text"] for b in blocks}


def test_expected_contexts_present():
    contexts = {b["name"] for b in load_ext_blocks()}
    expected = {
        "t1-internal", "t2-internal", "t1-hints", "t2-hints",
        "from-tdm-gateway", "pickup-target", "click-to-call",
        "qualidade-chamada", "solicitar-callback", "callback-connect",
        "pesquisa-satisfacao", "selecionar-idioma", "rotear-horario",
        "atendente-virtual",
    }
    missing = expected - contexts
    assert not missing, f"Contextos esperados ausentes: {missing}"


def test_receptionist_extension_1000_routes_to_web_endpoint():
    """
    Com múltiplas telefonistas (backlog #8), o ramal 1000 vira a
    entrada da fila (round-robin entre quem estiver logada), não mais
    um Dial() fixo pra uma única pessoa.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["t1-internal"].replace(" ", "")
    assert "exten=>1000,1," in text
    exten_start = text.index("exten=>1000,1,")
    exten_end = text.index("exten=>", exten_start + 1)
    assert "Queue(${FILA_IDIOMA},c)" in text[exten_start:exten_end]


def test_unmatched_incoming_calls_go_into_the_ura():
    """
    Chamadas do gateway TDM sem DID mapeado entram na URA (backlog
    #17) - a URA decide, por horário/feriado, se toca a fila direto
    ou uma mensagem de fora de expediente.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    fallback_block = blocks["from-tdm-gateway"]
    assert "_X." in fallback_block
    assert "Goto(ura-principal,s,1)" in fallback_block.replace(" ", "")


def test_pickup_target_context_dials_receptionist():
    """
    O contexto usado pelo pickup dirigido (Redirect via AMI) precisa
    ter uma entrada por telefonista - o Redirect especifica QUAL
    ramal deve receber a chamada puxada (backlog #8).
    """
    blocks = blocks_as_dict(load_ext_blocks())
    pickup_block = blocks["pickup-target"].replace(" ", "")
    assert "exten=>t1-recepcao,1,Set(CHANNEL(hangup_handler_push)" in pickup_block
    assert "Dial(PJSIP/t1-recepcao,20,g)" in pickup_block
    assert "exten=>t1-recepcao-2,1,Set(CHANNEL(hangup_handler_push)" in pickup_block
    assert "Dial(PJSIP/t1-recepcao-2,20,g)" in pickup_block


def test_admin_panel_dynamic_extensions_are_included():
    """
    Sem esses #include, os ramais criados pelo painel de administração
    (backlog #10/#38) nunca aparecem no dialplan de verdade, mesmo que
    o admin-api tenha gerado o arquivo certinho. Um arquivo por tenant
    (backlog #38) - senão ramal do tenant 2 vazaria pro dialplan do
    tenant 1.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    assert "#include extensions_dynamic_dial-t1.conf" in blocks["t1-internal"]
    assert "#include extensions_dynamic_hints-t1.conf" in blocks["t1-hints"]
    assert "#include extensions_dynamic_dial-t2.conf" in blocks["t2-internal"]
    assert "#include extensions_dynamic_hints-t2.conf" in blocks["t2-hints"]


def test_direct_operator_extensions_are_recorded():
    """
    Os ramais diretos de cada telefonista (1010/1011, uso interno da
    equipe) precisam gravar via MixMonitor, já que não passam pela
    fila (que grava sozinha via monitor-type).
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["t1-internal"]
    assert "1010" in text and "MixMonitor(" in text
    assert "1011" in text and "Dial(PJSIP/t1-recepcao-2" in text


def test_receptionist_calls_are_recorded():
    """
    Os dois pontos onde a telefonista fala diretamente com alguém
    fora do fluxo de fila (dial direto no 1000, e a chamada puxada da
    fila) precisam gravar via MixMonitor - a fila em si já grava
    sozinha via monitor-type no queues.conf.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    assert "MixMonitor(" in blocks["t1-internal"]
    assert "MixMonitor(" in blocks["pickup-target"]


def test_receptionist_calls_push_quality_hangup_handler():
    """
    Sem o hangup_handler_push, o monitoramento de qualidade (backlog
    #34) nunca roda - as estatísticas RTCP simplesmente não são
    coletadas em nenhuma chamada.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    for context_name in ("t1-internal", "pickup-target"):
        text = blocks[context_name].replace(" ", "")
        assert "CHANNEL(hangup_handler_push)=qualidade-chamada,s,1" in text


def test_quality_context_reads_rtcp_and_sends_user_event():
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["qualidade-chamada"].replace(" ", "")
    assert "UserEvent(QualityStats" in text
    assert "CHANNEL(rtcp,rxjitter)" in text
    assert "CHANNEL(rtcp,rxploss)" in text
    assert "CHANNEL(rtcp,rtt)" in text
    assert "Return()" in text


def test_ura_offers_callback_option():
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["horario-comercial"].replace(" ", "")
    assert "exten=>9,1,Goto(solicitar-callback,s,1)" in text


def test_callback_request_context_sends_user_event_with_caller_id():
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["solicitar-callback"].replace(" ", "")
    assert "UserEvent(CallbackRequest" in text
    assert "CallerIDNum=${CALLERID(num)}" in text


def test_callback_connect_context_dials_tenant_specific_receptionist():
    """
    Backlog #38 (multi-tenant completo): callback-connect precisa
    discar pro atendente do TENANT certo (via ${TENANT}, passado pelo
    Originate do queue-api), não sempre pro tenant 1 fixo.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["callback-connect"].replace(" ", "")
    assert "Dial(PJSIP/${TENANT}-recepcao" in text
    assert 'Set(TENANT=${IF($["${TENANT}"=""]?t1:${TENANT})})' in text


def test_customer_stays_on_line_after_agent_hangs_up():
    """
    Sem a opção "c" (Queue) / "g" (Dial), o Asterisk derruba a
    chamada do CLIENTE assim que a telefonista desliga - a pesquisa
    de satisfação nunca rodaria.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["t1-internal"].replace(" ", "")
    assert "Queue(${FILA_IDIOMA},c)" in text
    assert "Dial(PJSIP/t1-recepcao,20,g)" in text
    assert "Dial(PJSIP/t1-recepcao-2,20,g)" in text

    pickup_text = blocks["pickup-target"].replace(" ", "")
    assert "Dial(PJSIP/t1-recepcao,20,g)" in pickup_text
    assert "Dial(PJSIP/t1-recepcao-2,20,g)" in pickup_text


def test_no_answer_falls_back_automatically_instead_of_giving_up():
    """
    Backlog #28 ("transferência inteligente... retorno automático se
    ninguém atender"): se o ramal direto (1010/1011/pickup) NÃO foi
    atendido, a chamada precisa voltar pra fila geral (1000) - não
    pode simplesmente ir pra pesquisa de satisfação de uma conversa
    que nunca aconteceu.
    """
    blocks = blocks_as_dict(load_ext_blocks())

    for context_name, dial_line in [
        ("t1-internal", "Dial(PJSIP/t1-recepcao,20,g)"),
        ("t1-internal", "Dial(PJSIP/t1-recepcao-2,20,g)"),
        ("pickup-target", "Dial(PJSIP/t1-recepcao,20,g)"),
        ("pickup-target", "Dial(PJSIP/t1-recepcao-2,20,g)"),
    ]:
        text = blocks[context_name].replace(" ", "")
        dial_pos = text.index(dial_line)
        answer_check_pos = text.index('DIALSTATUS}"="ANSWER"', dial_pos)
        fallback_pos = text.index("Goto(t1-internal,1000,1)", answer_check_pos)
        assert dial_pos < answer_check_pos < fallback_pos


def test_queue_only_surveys_if_actually_answered():
    """
    Mesma lógica pro Queue(): só pesquisa satisfação se
    QUEUESTATUS=CONTINUE (agente atendeu e desligou) - senão cai na
    caixa de recado, não numa pesquisa de conversa inexistente.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["t1-internal"].replace(" ", "")
    assert 'QUEUESTATUS}"="CONTINUE"' in text
    assert "VoiceMail(" in text


def test_survey_context_reads_digit_and_sends_user_event_with_operator():
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["pesquisa-satisfacao"].replace(" ", "")
    assert "Read(NOTA,custom/menu-satisfacao,1" in text
    assert "UserEvent(SatisfactionSurvey" in text
    assert "Nota=${NOTA}" in text
    assert "Operator=${DIALEDPEERNAME}" in text


def test_survey_handles_no_response():
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["pesquisa-satisfacao"].replace(" ", "")
    assert 'GotoIf($["${NOTA}"="' in text or "sem-resposta" in text


def test_click_to_call_context_dials_via_tdm_gateway():
    """
    O contexto usado pelo click-to-call (Originate via AMI, disparado
    pelo CRM) precisa realmente discar pro número do cliente através
    do tronco - senão o CRM "liga" e nada acontece do lado de fora.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    click_block = blocks["click-to-call"]
    assert "Dial(PJSIP/${EXTEN}@gateway-tdm" in click_block


def test_outbound_calls_check_blocklist_before_dialing():
    """
    Chamada de saída (backlog #14) precisa checar a lista de bloqueio
    (AstDB, por tenant - backlog #38) ANTES de discar - senão o
    número bloqueado pelo painel de administração continua discando
    normalmente.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["t1-internal"].replace(" ", "")
    exten_pos = text.index("exten=>_0.,1,")
    blocklist_check_pos = text.index("DB(blocklist-t1/", exten_pos)
    dial_pos = text.index("Dial(PJSIP/${DESTINO}@gateway-tdm,30)", exten_pos)
    assert exten_pos < blocklist_check_pos < dial_pos


def test_tenant2_outbound_calls_use_independent_blocklist():
    """
    Backlog #38: bloquear um número no tenant 1 não pode afetar o
    tenant 2 - cada um precisa da própria família AstDB.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["t2-internal"].replace(" ", "")
    assert "DB(blocklist-t2/" in text
    assert "DB(blocklist-t1/" not in text


def test_blocked_number_route_uses_congestion_not_normal_dial():
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["t1-internal"]
    blocked_start = text.index("exten => numero-bloqueado,1,")
    blocked_end = text.index("exten =>", blocked_start + 1)
    blocked_block = text[blocked_start:blocked_end].replace(" ", "")
    assert "Congestion()" in blocked_block
    assert "Dial(PJSIP/" not in blocked_block


def test_alternate_route_uses_second_trunk():
    """
    Prefixo "00" precisa rotear pelo tronco alternativo
    (gateway-tdm-2), não pelo padrão - é isso que torna isso uma
    "rota diferente por prefixo", não só um bloqueio.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["t1-internal"]
    alt_start = text.index("exten => rota-alternativa,1,")
    alt_end = text.index("exten =>", alt_start + 1)
    alt_block = text[alt_start:alt_end].replace(" ", "")
    assert "@gateway-tdm-2," in alt_block
    assert "@gateway-tdm," not in alt_block


def test_ura_checks_holiday_mode_before_business_hours():
    """
    O modo feriado (ligado manualmente pelo painel, por tenant -
    backlog #38) precisa ter prioridade sobre o horário comercial
    normal - senão "feriado numa segunda de manhã" tocaria o menu de
    horário comercial mesmo assim. Isso agora vive em
    [rotear-horario], depois da seleção de idioma (backlog #30).
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["rotear-horario"].replace(" ", "")
    holiday_check_pos = text.index("DB(config-${TENANT}/modo-feriado")
    time_check_pos = text.index("GotoIfTime(")
    assert holiday_check_pos < time_check_pos


def test_vip_check_has_priority_over_language_selection():
    """
    Cliente VIP (backlog #28) precisa ser checado ANTES até da
    seleção de idioma (backlog #30) - é a regra de maior prioridade
    de todas, não faz sentido perguntar idioma pra quem já tem rota
    direta definida. Lista de VIP é por tenant (backlog #38).
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["ura-principal"].replace(" ", "")
    vip_check_pos = text.index("DB(vip-${TENANT}/")
    language_check_pos = text.index("Background(custom/menu-idioma)")
    assert vip_check_pos < language_check_pos


def test_vip_route_uses_dynamic_extension_and_tenant_from_astdb():
    """
    Backlog #38: o destino final precisa respeitar o TENANT da
    chamada, não sempre cair em t1-internal.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["ura-principal"].replace(" ", "")
    assert "Goto(${TENANT}-internal,${VIP_DESTINO},1)" in text


def test_ura_routes_digit_1_and_2_differently():
    """
    Backlog #38: os dois destinos usam ${TENANT} - a URA é um
    contexto único e compartilhado entre tenants, não existe uma
    URA duplicada por tenant.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["horario-comercial"].replace(" ", "")
    assert "exten=>1,1,Goto(${TENANT}-internal,1000,1)" in text
    assert "exten=>2,1,Goto(${TENANT}-internal,1010,1)" in text


def test_after_hours_and_holiday_contexts_go_to_voicemail():
    blocks = blocks_as_dict(load_ext_blocks())
    for context_name in ("fora-horario", "feriado"):
        text = blocks[context_name].replace(" ", "")
        assert "VoiceMail(${TENANT}-1001@${TENANT}" in text
        assert "Background(custom/" in text


def test_ura_test_extension_exists_for_internal_testing():
    """Cada tenant tem sua própria extensão de teste (700) que define ${TENANT} antes de entrar na URA compartilhada."""
    blocks = blocks_as_dict(load_ext_blocks())
    t1_text = blocks["t1-internal"].replace(" ", "")
    assert "exten=>700,1,Set(TENANT=t1)" in t1_text
    t2_text = blocks["t2-internal"].replace(" ", "")
    assert "exten=>700,1,Set(TENANT=t2)" in t2_text


def test_language_selection_offers_three_languages():
    """
    Backlog #38: cada idioma monta a fila do TENANT certo
    (fila-${TENANT}[-idioma]) - contexto único, compartilhado.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["selecionar-idioma"].replace(" ", "")
    assert "exten=>pt,1,Set(FILA_IDIOMA=fila-${TENANT})" in text
    assert "exten=>en,1,Set(FILA_IDIOMA=fila-${TENANT}-en)" in text
    assert "exten=>es,1,Set(FILA_IDIOMA=fila-${TENANT}-es)" in text


def test_language_selection_sets_language_specific_menu_audio():
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["selecionar-idioma"].replace(" ", "")
    assert "MENU_PRINCIPAL=custom/menu-principal-pt" in text
    assert "MENU_PRINCIPAL=custom/menu-principal-en" in text
    assert "MENU_PRINCIPAL=custom/menu-principal-es" in text


def test_business_hours_menu_uses_selected_language_audio():
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["horario-comercial"].replace(" ", "")
    assert "Background(${MENU_PRINCIPAL})" in text


def test_direct_dial_to_1000_defaults_to_tenant_specific_portuguese_queue():
    """
    Ramal 1000 discado diretamente (sem passar pela URA - ex: ramal
    interno ou teste) precisa cair na fila em português do PRÓPRIO
    tenant por padrão (backlog #38) - t1-internal cai em fila-t1,
    t2-internal cai em fila-t2, nunca cruzando tenants.
    """
    blocks = blocks_as_dict(load_ext_blocks())

    for context_name, tenant in (("t1-internal", "t1"), ("t2-internal", "t2")):
        text = blocks[context_name].replace(" ", "")
        exten_start = text.index("exten=>1000,1,")
        exten_end = text.index("exten=>", exten_start + 1)
        block_text = text[exten_start:exten_end]
        expected_tenant_default = 'TENANT=${IF($["${TENANT}"=""]?' + tenant + ':${TENANT})})'
        assert expected_tenant_default in block_text
        assert 'FILA_IDIOMA=${IF($["${FILA_IDIOMA}"=""]?fila-${TENANT}' in block_text


def test_virtual_attendant_test_extension_exists():
    """Cada tenant define ${TENANT} antes de entrar no atendente virtual compartilhado (backlog #38)."""
    blocks = blocks_as_dict(load_ext_blocks())
    t1_text = blocks["t1-internal"].replace(" ", "")
    assert "exten=>650,1,Set(TENANT=t1)" in t1_text
    t2_text = blocks["t2-internal"].replace(" ", "")
    assert "exten=>650,1,Set(TENANT=t2)" in t2_text


def test_virtual_attendant_runs_agi_and_routes_by_intent():
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["atendente-virtual"].replace(" ", "")
    assert "AGI(atendente_virtual.py)" in text
    assert "INTENT_DESTINO" in text


def test_virtual_attendant_falls_back_to_general_queue_when_agi_sets_nothing():
    """
    Se o AGI não conseguir definir ${INTENT_DESTINO} por qualquer
    motivo (ai-worker fora do ar, IA desligada, etc.), a chamada
    precisa cair na fila geral do TENANT certo - nunca travar sem
    destino nenhum, e nunca cair no tenant errado (backlog #38).
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["atendente-virtual"].replace(" ", "")
    assert 'GotoIf($["${INTENT_DESTINO}"!=""]?rotear,1)' in text
    assert "Goto(${TENANT}-internal,1000,1)" in text


def test_simultaneous_ring_group_dials_all_members_at_once():
    """
    Grupo simultâneo (backlog #18) precisa usar '&' pra discar todos
    os membros de uma vez só - um único Dial(), não vários separados.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["t1-internal"].replace(" ", "")
    ring_group_start = text.index("exten=>900,1,")
    ring_group_end = text.index("exten=>", ring_group_start + 1)
    ring_group_block = text[ring_group_start:ring_group_end]
    assert "Dial(PJSIP/t1-1001&PJSIP/t1-1002&PJSIP/t1-recepcao,20)" in ring_group_block


def test_sequential_ring_group_dials_members_one_at_a_time():
    """
    Grupo em sequência (backlog #18) precisa de um Dial() separado por
    membro (prioridades diferentes), não um Dial() só com '&' -
    senão vira o mesmo comportamento do grupo simultâneo.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["t1-internal"].replace(" ", "")
    ring_group_start = text.index("exten=>901,1,")
    remaining = text[ring_group_start + 1:]
    next_exten_offset = remaining.find("exten=>")
    ring_group_end = ring_group_start + 1 + next_exten_offset if next_exten_offset != -1 else len(text)
    ring_group_block = text[ring_group_start:ring_group_end]
    assert ring_group_block.count("Dial(PJSIP/") == 3
    assert "&" not in ring_group_block


def test_ring_groups_have_combined_hints():
    blocks = blocks_as_dict(load_ext_blocks())
    hints_text = blocks["t1-hints"].replace(" ", "")
    assert "exten=>900,hint,PJSIP/t1-1001&PJSIP/t1-1002&PJSIP/t1-recepcao" in hints_text
    assert "exten=>901,hint,PJSIP/t1-1001&PJSIP/t1-1002&PJSIP/t1-recepcao" in hints_text


def test_every_hint_references_an_endpoint_that_exists_in_pjsip_conf():
    """
    Todo 'hint,PJSIP/xxx' em extensions.conf precisa ter um endpoint
    'xxx' de verdade no pjsip.conf - senão o BLF simplesmente não
    funciona e ninguém percebe até testar na mão. Hints combinados
    (ex: PJSIP/a&PJSIP/b, usados pra representar um grupo) são
    separados antes de checar cada dispositivo individualmente.
    """
    pjsip_blocks = parse_blocks(PJSIP_CONF)
    endpoint_names = {b["name"] for b in blocks_by_type(pjsip_blocks, "endpoint")}

    hint_targets = set()
    for block in load_ext_blocks():
        for match in HINT_RE.finditer(block["text"]):
            for device in match.group(2).split("&"):
                if device.startswith("PJSIP/"):
                    hint_targets.add(device[len("PJSIP/"):])

    assert hint_targets, "Nenhum hint encontrado - verifique se o arquivo não quebrou"
    missing = hint_targets - endpoint_names
    assert not missing, f"Hints apontando para endpoints inexistentes: {missing}"


def test_tenants_do_not_share_extension_numbers_in_same_context():
    """
    Garante que dentro de um MESMO contexto de tenant não existem
    números de ramal duplicados (indicaria erro de copiar/colar entre
    tenants).
    """
    blocks = blocks_as_dict(load_ext_blocks())
    for context_name in ("t1-internal", "t2-internal"):
        text = blocks[context_name]
        extens = re.findall(r"exten\s*=>\s*(\d+),1,", text)
        assert len(extens) == len(set(extens)), (
            f"Números de ramal duplicados no contexto {context_name}: {extens}"
        )


# ---------- Multi-tenant completo (backlog #38) ----------

def test_tenant2_has_queue_entry_point_mirroring_tenant1():
    """
    Tenant 2 precisa ter a mesma entrada de fila que o tenant 1 -
    senão "multi-tenant" seria só isolamento de ramal comum, sem
    nenhuma das funcionalidades avançadas construídas depois.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["t2-internal"].replace(" ", "")
    assert "exten=>1000,1," in text
    assert "Queue(${FILA_IDIOMA},c)" in text
    assert 'QUEUESTATUS}"="CONTINUE"' in text


def test_tenant2_has_direct_operator_extensions_with_survey_and_fallback():
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["t2-internal"].replace(" ", "")
    assert "Dial(PJSIP/t2-recepcao,20,g)" in text
    assert "Dial(PJSIP/t2-recepcao-2,20,g)" in text
    assert "Goto(t2-internal,1000,1)" in text  # retorno automático (backlog #28) também no tenant 2


def test_tenant2_has_test_extensions_for_ura_queue_and_virtual_attendant():
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["t2-internal"].replace(" ", "")
    assert "exten=>800,1,Queue(fila-t2)" in text
    assert "exten=>700,1,Set(TENANT=t2)" in text
    assert "exten=>650,1,Set(TENANT=t2)" in text


def test_pickup_target_has_entries_for_both_tenants():
    """
    Backlog #38: pickup dirigido (manual 08/14) precisa funcionar pra
    telefonistas de QUALQUER tenant, não só do tenant 1.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["pickup-target"].replace(" ", "")
    for operator in ("t1-recepcao", "t1-recepcao-2", "t2-recepcao", "t2-recepcao-2"):
        assert f"exten=>{operator},1," in text


def test_t2_hints_mirror_t1_hints_structure():
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["t2-hints"].replace(" ", "")
    assert "1000,hint,PJSIP/t2-recepcao&PJSIP/t2-recepcao-2" in text
    assert "1010,hint,PJSIP/t2-recepcao" in text
    assert "1011,hint,PJSIP/t2-recepcao-2" in text


def test_from_tdm_gateway_sets_tenant_before_entering_shared_contexts():
    """
    ${TENANT} precisa ser definido ANTES de entrar em qualquer
    contexto compartilhado (URA, atendente virtual) - senão essas
    variáveis ficam vazias e tudo cai no valor padrão (t1) mesmo pra
    chamadas que deveriam ser do tenant 2.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["from-tdm-gateway"].replace(" ", "")
    t1_pos = text.index("exten=>5511900001111,1,")
    t1_set_pos = text.index("Set(TENANT=t1)", t1_pos)
    t1_goto_pos = text.index("Goto(t1-internal,1001,1)", t1_pos)
    assert t1_pos < t1_set_pos < t1_goto_pos

    t2_pos = text.index("exten=>5511900002222,1,")
    t2_set_pos = text.index("Set(TENANT=t2)", t2_pos)
    t2_goto_pos = text.index("Goto(t2-internal,1001,1)", t2_pos)
    assert t2_pos < t2_set_pos < t2_goto_pos


def test_unmapped_did_looks_up_tenant_dynamically_via_astdb():
    """
    Backlog #39 (wizard de preparação de ambiente): o "pega-tudo" de
    DID não mapeado explicitamente precisa consultar o AstDB (família
    "tenant-did", registrada pelo wizard ao criar um tenant novo) ANTES
    de cair no padrão (t1) - senão criar um tenant novo pelo wizard
    nunca teria efeito nenhum no roteamento de chamada de entrada.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["from-tdm-gateway"].replace(" ", "")
    catch_all_pos = text.index("exten=>_X.,1,")
    lookup_pos = text.index("DB(tenant-did/${EXTEN})", catch_all_pos)
    default_pos = text.index('TENANT=${IF($["${TENANT}"=""]?t1', catch_all_pos)
    assert catch_all_pos < lookup_pos < default_pos


def test_extensions_conf_includes_wizard_created_tenants_via_wildcard():
    """
    Backlog #39: criar um tenant novo NUNCA deve exigir editar
    extensions.conf de novo - o #include com wildcard precisa estar
    presente pra qualquer arquivo novo em extensions_tenants/ ser
    carregado automaticamente.
    """
    content = EXTENSIONS_CONF.read_text(encoding="utf-8")
    assert "#include extensions_tenants/*.conf" in content


# ---------- Aviso de gravação / conformidade LGPD (backlog #40) ----------

def test_recording_consent_announcement_plays_before_every_recorded_call():
    """
    LGPD exige aviso/consentimento pra gravação de chamada. Todo
    ponto que grava (fila, ramais diretos da telefonista) precisa
    tocar o aviso ANTES de conectar - nos dois tenants, já que
    "colocar tudo pra multi-tenant" inclui conformidade também.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    for context_name in ("t1-internal", "t2-internal"):
        text = blocks[context_name].replace(" ", "")
        assert text.count("Playback(custom/aviso-gravacao)") == 3, (
            f"{context_name} deveria ter o aviso nos 3 pontos gravados (1000/1010/1011)"
        )


def test_recording_consent_announcement_plays_before_recording_starts():
    """
    O aviso precisa vir ANTES do MixMonitor/Queue começar a gravar de
    verdade - avisar depois que já gravou não cumpre o propósito.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["t1-internal"].replace(" ", "")

    exten_start = text.index("exten=>1010,1,")
    exten_end = text.index("exten=>", exten_start + 1)
    block_text = text[exten_start:exten_end]
    playback_pos = block_text.index("Playback(custom/aviso-gravacao)")
    mixmonitor_pos = block_text.index("MixMonitor(")
    assert playback_pos < mixmonitor_pos


# ---------- Monitoramento de chamada (backlog #42) ----------

def test_both_tenants_have_monitoring_prefixes():
    """Cada tenant precisa dos 3 prefixos (*81 escuta, *82 sussurro, *83 intercalação)."""
    blocks = blocks_as_dict(load_ext_blocks())
    for context_name, tenant in (("t1-internal", "t1"), ("t2-internal", "t2")):
        text = blocks[context_name].replace(" ", "")
        for prefix, mode in (("*81", "listen"), ("*82", "whisper"), ("*83", "barge")):
            pattern = f"exten=>_{prefix}X.,1,Set(TENANT={tenant})"
            assert pattern in text, f"{context_name} sem o prefixo {prefix}"
            block_start = text.index(pattern)
            remaining = text[block_start + 1:]
            next_exten_offset = remaining.find("exten=>")
            block_end = block_start + 1 + next_exten_offset if next_exten_offset != -1 else len(text)
            assert f"MONITOR_MODE={mode}" in text[block_start:block_end]


def test_monitoring_blocked_without_pin_configured():
    """
    Sem PIN configurado (AstDB vazio), o monitoramento precisa ficar
    bloqueado por completo - desligado por padrão, mesmo padrão de
    segurança do resto do projeto.
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["chamada-monitorada"].replace(" ", "")
    pin_check_pos = text.index("DB(monitoring-pin-${TENANT}/pin)")
    empty_check_pos = text.index('GotoIf($["${PIN_ESPERADO}"=""]?sem-configuracao,1)')
    assert pin_check_pos < empty_check_pos


def test_pin_is_validated_before_authorizing_chanspy():
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["chamada-monitorada"].replace(" ", "")
    read_pos = text.index("Read(PIN_DIGITADO,")
    compare_pos = text.index('PIN_DIGITADO}"="${PIN_ESPERADO}', read_pos)
    authorized_pos = text.index("exten=>autorizado,1,", compare_pos)
    assert read_pos < compare_pos < authorized_pos


def test_all_three_modes_use_correct_chanspy_options():
    """
    'q' silencioso nos 3 modos, 'w' só no sussurro, 'B' só na
    intercalação - trocar essas letras muda completamente o
    comportamento (sussurro vazando pro cliente seria grave).
    """
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["chamada-monitorada"].replace(" ", "")
    assert "ChanSpy(${MONITOR_CHANNEL},q)" in text
    assert "ChanSpy(${MONITOR_CHANNEL},qw)" in text
    assert "ChanSpy(${MONITOR_CHANNEL},qB)" in text


def test_invalid_monitoring_target_does_not_silently_spy_on_nothing():
    blocks = blocks_as_dict(load_ext_blocks())
    text = blocks["chamada-monitorada"].replace(" ", "")
    assert 'GotoIf($["${MONITOR_CHANNEL}"=""]?destino-invalido,1)' in text
