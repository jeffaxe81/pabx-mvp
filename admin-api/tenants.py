"""
Wizard de preparação de ambiente por tenant (backlog #39). Cria um
tenant novo de ponta a ponta - telefonistas web, filas (padrão +
inglês + espanhol), contextos de dialplan, caixas de voz e o
mapeamento de DID - sem precisar editar nenhum .conf na mão (só os
dois exemplos originais, t1 e t2, foram feitos manualmente).

Lógica pura de validação e geração de texto aqui - a escrita em disco
e a chamada AMI (registrar o DID no AstDB) ficam isoladas no
server.py, mesmo padrão do resto do projeto.
"""
import json
import os
import re
import secrets
import tempfile
from pathlib import Path

TENANT_ID_RE = re.compile(r"^t([3-9]|[1-9][0-9]+)$")  # t3, t4, ... - t1/t2 já existem manualmente
DID_RE = re.compile(r"^[0-9]{8,15}$")
DISPLAY_NAME_RE = re.compile(r"^.{2,60}$")

AUTO_GENERATED_HEADER = (
    "; ARQUIVO GERADO AUTOMATICAMENTE PELO WIZARD DE PREPARAÇÃO DE AMBIENTE.\n"
    "; NÃO EDITE NA MÃO - qualquer alteração aqui é sobrescrita na\n"
    "; próxima vez que um tenant for criado/removido pelo wizard.\n\n"
)


def load_tenants(path) -> list:
    path = Path(path)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_tenants(path, tenants: list):
    """Publica JSON de forma atômica para evitar arquivo truncado."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent,
            prefix=f".{destination.name}.", delete=False,
        ) as handle:
            temporary = handle.name
            json.dump(tenants, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


def _valid_existing_records(existing) -> bool:
    """Uma lista corrompida não pode liberar criação/remoção por engano."""
    return (
        isinstance(existing, list)
        and all(
            isinstance(item, dict)
            and isinstance(item.get("tenant_id"), str)
            and isinstance(item.get("did"), str)
            for item in existing
        )
    )


def parse_static_inbound_dids(dialplan_text: str) -> set:
    """Obtém DIDs fixos do contexto Asterisk [from-tdm-gateway].

    O wizard não pode registrar no AstDB um DID que já tem roteamento
    explícito neste contexto: essa regra terá precedência.
    """
    if not isinstance(dialplan_text, str):
        raise ValueError("dialplan ilegível")
    context_found = False
    in_context = False
    dids = set()
    for line in dialplan_text.splitlines():
        stripped = line.strip()
        if stripped.startswith(";") or not stripped:
            continue
        section = re.fullmatch(r"\[([^\]]+)\]", stripped)
        if section:
            in_context = section.group(1).strip() == "from-tdm-gateway"
            context_found = context_found or in_context
            continue
        if not in_context:
            continue
        match = re.match(r"^exten\s*=>\s*([0-9]{8,15})\s*,\s*1\s*,", stripped)
        if match:
            dids.add(match.group(1))
    if not context_found:
        raise ValueError("contexto from-tdm-gateway ausente")
    return dids


def validate_tenant_creation_input(data: dict, existing: list, reserved_dids=()):
    """Valida JSON antes de gerar arquivos Asterisk ou registrar DID no AMI."""
    if not isinstance(data, dict):
        return False, "dados do tenant devem ser um objeto JSON", None
    if not _valid_existing_records(existing):
        return False, "cadastro de tenants existente é inválido", None

    raw_tenant = data.get("tenant_id")
    if not isinstance(raw_tenant, str):
        return False, "id do tenant deve ser texto", None
    if "\r" in raw_tenant or "\n" in raw_tenant:
        return False, "id do tenant inválido", None
    tenant_id = raw_tenant.strip().lower()
    if not TENANT_ID_RE.fullmatch(tenant_id):
        return False, "id do tenant deve seguir o padrão 't3', 't4', ... (t1/t2 já existem)", None
    if any(t["tenant_id"] == tenant_id for t in existing):
        return False, f"o tenant '{tenant_id}' já foi criado", None

    raw_did = data.get("did")
    if not isinstance(raw_did, str):
        return False, "DID inválido (deve ser texto)", None
    raw_did = raw_did.strip()
    # Aceitar formatação telefônica conhecida, mas não letras ou lixo
    # arbitrário que antes era silenciosamente descartado por re.sub().
    if not re.fullmatch(r"[0-9+().\-\s]+", raw_did):
        return False, "DID inválido (caracteres não permitidos)", None
    did = re.sub(r"[^0-9]", "", raw_did)
    if not DID_RE.fullmatch(did):
        return False, "DID inválido (só dígitos, 8-15 caracteres)", None
    if any(t["did"] == did for t in existing):
        return False, f"o DID '{did}' já está registrado pra outro tenant", None
    if did in reserved_dids:
        return False, f"o DID '{did}' já possui rota estática no Asterisk", None

    raw_name = data.get("display_name")
    if not isinstance(raw_name, str):
        return False, "nome de exibição deve ser texto", None
    display_name = raw_name.strip()
    if not DISPLAY_NAME_RE.fullmatch(display_name) or not display_name.isprintable():
        return False, "nome de exibição obrigatório (2-60 caracteres, sem controles)", None

    return True, None, {
        "tenant_id": tenant_id,
        "did": did,
        "display_name": display_name,
    }


def validate_tenant_removal(tenant_id: str, existing: list):
    """Exclusão só aceita IDs t3+ de registros válidos do wizard."""
    if not isinstance(tenant_id, str):
        return False, "id do tenant deve ser texto", None
    if "\r" in tenant_id or "\n" in tenant_id:
        return False, "id do tenant inválido", None
    tenant_id = tenant_id.strip().lower()
    if tenant_id in ("t1", "t2"):
        return False, "t1/t2 são exemplos estáticos do projeto - não gerenciados pelo wizard, não podem ser removidos por aqui", None
    if not TENANT_ID_RE.fullmatch(tenant_id):
        return False, "id do tenant inválido", None
    if not _valid_existing_records(existing):
        return False, "cadastro de tenants existente é inválido", None

    match = next((t for t in existing if t["tenant_id"] == tenant_id), None)
    if not match:
        return False, f"tenant '{tenant_id}' não encontrado", None

    return True, None, match


def generate_tenant_credentials(tenant_id: str) -> dict:
    """Gera senhas SIP fortes e distintas para as duas telefonistas."""
    if not isinstance(tenant_id, str) or not TENANT_ID_RE.fullmatch(tenant_id):
        raise ValueError("tenant inválido para credenciais SIP")
    return {
        f"{tenant_id}-recepcao": secrets.token_urlsafe(24),
        f"{tenant_id}-recepcao-2": secrets.token_urlsafe(24),
    }


def render_tenant_pjsip(tenant_id: str, credentials=None) -> str:
    """Duas telefonistas WebRTC com segredos exclusivos, não previsíveis."""
    if credentials is None:
        credentials = generate_tenant_credentials(tenant_id)
    if not isinstance(credentials, dict):
        raise ValueError("credenciais SIP inválidas")
    for name in (f"{tenant_id}-recepcao", f"{tenant_id}-recepcao-2"):
        password = credentials.get(name)
        if not isinstance(password, str) or not re.fullmatch(r"[A-Za-z0-9_-]{32,}", password):
            raise ValueError("senha SIP ausente ou insegura")
    blocks = [AUTO_GENERATED_HEADER]
    for suffix, line_number in (("", "1010"), ("-2", "1011")):
        name = f"{tenant_id}-recepcao{suffix}"
        blocks.append(f"""[{name}](endpoint-webrtc)
context={tenant_id}-internal
subscribe_context={tenant_id}-hints
auth={name}
aors={name}
callerid=Recepcao Web {"1" if suffix == "" else "2"} ({tenant_id.upper()}) <{line_number}>
mailboxes={name}@{tenant_id}

[{name}]
type=auth
auth_type=userpass
username={name}
password={credentials[name]}

[{name}]
type=aor
max_contacts=1
remove_existing=yes
""")
    return "\n".join(blocks)


def render_tenant_queues(tenant_id: str) -> str:
    """Fila padrão + inglês + espanhol, mesmo padrão de fila-t1/fila-t2."""
    queues = [
        (f"fila-{tenant_id}", [f"{tenant_id}-recepcao", f"{tenant_id}-recepcao-2"]),
        (f"fila-{tenant_id}-en", [f"{tenant_id}-recepcao"]),
        (f"fila-{tenant_id}-es", [f"{tenant_id}-recepcao-2"]),
    ]
    lines = [AUTO_GENERATED_HEADER]
    for queue_name, members in queues:
        member_lines = "\n".join(f"member => PJSIP/{m}" for m in members)
        lines.append(f"""[{queue_name}]
musicclass = default
strategy = rrmemory
timeout = 15
retry = 5
weight = 0
joinempty = yes
leavewhenempty = no
monitor-type = mixmonitor
{member_lines}
""")
    return "\n".join(lines)


def render_tenant_extensions(tenant_id: str) -> str:
    """
    Contextos [tenant-internal] e [tenant-hints] completos, espelhando
    a estrutura de [t1-internal]/[t2-internal] (fila, operadores
    diretos com retorno automático, extensões de teste, #include pros
    ramais que forem criados depois pelo painel de administração).
    """
    return f"""{AUTO_GENERATED_HEADER}[{tenant_id}-internal]
exten => 1000,1,Answer()
 same => n,Playback(custom/aviso-gravacao)
 same => n,Set(CHANNEL(hangup_handler_push)=qualidade-chamada,s,1)
 same => n,Set(TENANT={tenant_id})
 same => n,GotoIf($["${{FILA_IDIOMA}}" = "fila-{tenant_id}-en"]?idioma-autorizado)
 same => n,GotoIf($["${{FILA_IDIOMA}}" = "fila-{tenant_id}-es"]?idioma-autorizado)
 same => n,Set(FILA_IDIOMA=fila-{tenant_id})
 same => n(idioma-autorizado),NoOp(Fila validada para {tenant_id})
 same => n,Set(FILA_OVERFLOW=${{IF($["${{FILA_IDIOMA}}" = "fila-${{TENANT}}"]?:fila-${{TENANT}})}})
 same => n,Set(OVERFLOW_TIMEOUT=${{IF($["${{DB(config-${{TENANT}}/overflow-timeout-segundos)}}" = ""]?${{OVERFLOW_TIMEOUT_SECONDS}}:${{DB(config-${{TENANT}}/overflow-timeout-segundos)}})}})
 same => n,Set(CDR(accountcode)={tenant_id})
 same => n,Queue(${{FILA_IDIOMA}},c,,,${{OVERFLOW_TIMEOUT}})
 same => n,GotoIf($["${{QUEUESTATUS}}" = "CONTINUE"]?pesquisa-satisfacao,s,1)
 same => n,GotoIf($["${{QUEUESTATUS}}" = "TIMEOUT"]?fila-overflow,1)
 same => n,VoiceMail(${{TENANT}}-1001@${{TENANT}},u)
 same => n,Hangup()

; Overflow entre filas (backlog #45) - mesmo esquema de t1/t2
exten => fila-overflow,1,NoOp(Fila ${{FILA_IDIOMA}} sem resposta em ${{OVERFLOW_TIMEOUT_SECONDS}}s)
 same => n,GotoIf($["${{FILA_OVERFLOW}}" != ""]?fazer-overflow,1)
 same => n,VoiceMail(${{TENANT}}-1001@${{TENANT}},u)
 same => n,Hangup()

exten => fazer-overflow,1,NoOp(Transbordando de ${{FILA_IDIOMA}} pra ${{FILA_OVERFLOW}})
 same => n,Set(FILA_IDIOMA=${{FILA_OVERFLOW}})
 same => n,Goto(1000,1)

exten => 1010,1,Answer()
 same => n,Playback(custom/aviso-gravacao)
 same => n,Set(CHANNEL(hangup_handler_push)=qualidade-chamada,s,1)
 same => n,Set(CDR(accountcode)={tenant_id})
 same => n,MixMonitor(/var/spool/asterisk/monitor/${{STRFTIME(${{EPOCH}},,%Y%m%d-%H%M%S)}}-${{CALLERID(num)}}-{tenant_id}-1010.wav,b)
 same => n,Dial(PJSIP/{tenant_id}-recepcao,20,g)
 same => n,GotoIf($["${{DIALSTATUS}}" = "ANSWER"]?pesquisa-satisfacao,s,1)
 same => n,Goto({tenant_id}-internal,1000,1)

exten => 1011,1,Answer()
 same => n,Playback(custom/aviso-gravacao)
 same => n,Set(CHANNEL(hangup_handler_push)=qualidade-chamada,s,1)
 same => n,Set(CDR(accountcode)={tenant_id})
 same => n,MixMonitor(/var/spool/asterisk/monitor/${{STRFTIME(${{EPOCH}},,%Y%m%d-%H%M%S)}}-${{CALLERID(num)}}-{tenant_id}-1011.wav,b)
 same => n,Dial(PJSIP/{tenant_id}-recepcao-2,20,g)
 same => n,GotoIf($["${{DIALSTATUS}}" = "ANSWER"]?pesquisa-satisfacao,s,1)
 same => n,Goto({tenant_id}-internal,1000,1)

exten => 600,1,Answer()
 same => n,Echo()
 same => n,Hangup()

; *97 só pode abrir o mailbox do endpoint SIP autenticado.
exten => *97,1,Set(VM_ENDPOINT=${{CHANNEL(endpoint)}})
 same => n,GotoIf($["${{VM_ENDPOINT}}" = ""]?voicemail-negado)
 same => n,GotoIf($["${{PJSIP_ENDPOINT(${{VM_ENDPOINT}},context)}}" != "{tenant_id}-internal"]?voicemail-negado)
 same => n,GotoIf($["${{PJSIP_ENDPOINT(${{VM_ENDPOINT}},mailboxes)}}" != "${{VM_ENDPOINT}}@{tenant_id}"]?voicemail-negado)
 same => n,VoiceMailMain(${{VM_ENDPOINT}}@{tenant_id})
 same => n,Hangup()
 same => n(voicemail-negado),Hangup(21)

exten => _0.,1,Set(DESTINO=${{EXTEN:1}})
 same => n,GotoIf($["${{DB(blocklist-{tenant_id}/${{DESTINO}})}}" = "1"]?numero-bloqueado,1)
 same => n,Dial(PJSIP/${{DESTINO}}@gateway-tdm,30)
 same => n,Hangup()

exten => numero-bloqueado,1,NoOp(Chamada bloqueada pela regra de discagem: ${{DESTINO}})
 same => n,Congestion()
 same => n,Hangup()

exten => 800,1,Queue(fila-{tenant_id})
 same => n,Hangup()

exten => 700,1,Set(TENANT={tenant_id})
 same => n,Goto(ura-principal,s,1)

exten => 650,1,Set(TENANT={tenant_id})
 same => n,Goto(atendente-virtual,s,1)

; Sala de conferência ad-hoc (backlog #43) - mesmo esquema de t1/t2
exten => _40XXXX,1,Set(TENANT={tenant_id})
 same => n,Answer()
 same => n,ConfBridge(sala-${{TENANT}}-${{EXTEN:2}},default_bridge,default_user,default_menu)

; Ramais gerenciados pelo painel de administração (backlog #10/#38) -
; gerado pelo admin-api, não editar na mão.
#include generated/extensions_dynamic_dial-{tenant_id}.conf

[{tenant_id}-hints]
exten => 1000,hint,PJSIP/{tenant_id}-recepcao&PJSIP/{tenant_id}-recepcao-2
exten => 1010,hint,PJSIP/{tenant_id}-recepcao
exten => 1011,hint,PJSIP/{tenant_id}-recepcao-2
#include generated/extensions_dynamic_hints-{tenant_id}.conf
"""


def generate_tenant_voicemail_pins(tenant_id: str) -> dict:
    """Gera PINs numéricos independentes para caixas de voz de um tenant."""
    if not isinstance(tenant_id, str) or not TENANT_ID_RE.fullmatch(tenant_id):
        raise ValueError("tenant inválido para PIN de caixa postal")
    # A fila/URA pode encaminhar para tN-1001 quando ninguém atende.
    # Essa caixa deve existir mesmo sem um endpoint PJSIP tN-1001.
    names = (f"{tenant_id}-1001", f"{tenant_id}-recepcao",
             f"{tenant_id}-recepcao-2")
    pins = {}
    used = set()
    for name in names:
        pin = str(secrets.randbelow(90_000_000) + 10_000_000)
        while pin in used:
            pin = str(secrets.randbelow(90_000_000) + 10_000_000)
        pins[name] = pin
        used.add(pin)
    return pins


def render_tenant_voicemail(tenant_id: str, pins=None) -> str:
    """Configura correio de voz com PINs exclusivos, nunca 1234."""
    if not isinstance(tenant_id, str) or not TENANT_ID_RE.fullmatch(tenant_id):
        raise ValueError("tenant inválido para caixa postal")
    if pins is None:
        pins = generate_tenant_voicemail_pins(tenant_id)
    if not isinstance(pins, dict):
        raise ValueError("PINs de caixa postal inválidos")
    names = (f"{tenant_id}-1001", f"{tenant_id}-recepcao",
             f"{tenant_id}-recepcao-2")
    if set(pins) != set(names):
        raise ValueError("conjunto de caixas postais do tenant incompleto")
    for name in names:
        pin = pins[name]
        if not isinstance(pin, str) or not re.fullmatch(r"[1-9][0-9]{7}", pin):
            raise ValueError("PIN de caixa postal inseguro")
    if len(set(pins.values())) != len(names):
        raise ValueError("caixas postais não podem compartilhar PIN")
    return f"""{AUTO_GENERATED_HEADER}[{tenant_id}]
{tenant_id}-1001 => {pins[f"{tenant_id}-1001"]},{tenant_id.upper()} Caixa Fallback 1001
{tenant_id}-recepcao => {pins[f"{tenant_id}-recepcao"]},{tenant_id.upper()} Recepcao Web 1
{tenant_id}-recepcao-2 => {pins[f"{tenant_id}-recepcao-2"]},{tenant_id.upper()} Recepcao Web 2
#include generated/voicemail_dynamic_{tenant_id}.conf
"""


def render_tenant_parking(tenant_id: str) -> str:
    """
    Vaga de estacionamento de chamada (backlog #41) - mesmo padrão de
    número (75/76-95) usado em t1/t2, isolado no próprio contexto
    interno do tenant.
    """
    return f"""{AUTO_GENERATED_HEADER}[parkinglot-{tenant_id}]
context = {tenant_id}-internal
parkext = 75
parkpos = 76-95
parkinghints = yes
comebacktoorigin = yes
parkedmusicclass = default
"""
