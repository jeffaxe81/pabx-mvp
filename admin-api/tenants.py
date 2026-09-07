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
import re
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
    Path(path).write_text(json.dumps(tenants, indent=2, ensure_ascii=False), encoding="utf-8")


def validate_tenant_creation_input(data: dict, existing: list):
    """
    Valida os dados de um tenant novo. Retorna (ok, error_message,
    cleaned_data). t1 e t2 são os exemplos estáticos originais do
    projeto - o wizard só cria a partir de t3 em diante, de propósito
    (evita colidir com a configuração manual já existente).
    """
    tenant_id = (data.get("tenant_id") or "").strip().lower()
    if not TENANT_ID_RE.match(tenant_id):
        return False, "id do tenant deve seguir o padrão 't3', 't4', ... (t1/t2 já existem)", None

    if any(t["tenant_id"] == tenant_id for t in existing):
        return False, f"o tenant '{tenant_id}' já foi criado", None

    did = re.sub(r"[^0-9]", "", data.get("did") or "")
    if not DID_RE.match(did):
        return False, "DID inválido (só dígitos, 8-15 caracteres)", None

    if any(t["did"] == did for t in existing):
        return False, f"o DID '{did}' já está registrado pra outro tenant", None

    display_name = (data.get("display_name") or "").strip()
    if not DISPLAY_NAME_RE.match(display_name):
        return False, "nome de exibição obrigatório (2-60 caracteres)", None

    return True, None, {
        "tenant_id": tenant_id,
        "did": did,
        "display_name": display_name,
    }


def render_tenant_pjsip(tenant_id: str) -> str:
    """Duas telefonistas web, mesmo padrão de t1-recepcao/t2-recepcao."""
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
password=troque_esta_senha_web_{tenant_id}{suffix.replace('-', '_')}

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
 same => n,Set(TENANT=${{IF($["${{TENANT}}" = ""]?{tenant_id}:${{TENANT}})}})
 same => n,Set(FILA_IDIOMA=${{IF($["${{FILA_IDIOMA}}" = ""]?fila-${{TENANT}}:${{FILA_IDIOMA}})}})
 same => n,Queue(${{FILA_IDIOMA}},c)
 same => n,GotoIf($["${{QUEUESTATUS}}" = "CONTINUE"]?pesquisa-satisfacao,s,1)
 same => n,VoiceMail(${{TENANT}}-1001@${{TENANT}},u)
 same => n,Hangup()

exten => 1010,1,Answer()
 same => n,Playback(custom/aviso-gravacao)
 same => n,Set(CHANNEL(hangup_handler_push)=qualidade-chamada,s,1)
 same => n,MixMonitor(/var/spool/asterisk/monitor/${{STRFTIME(${{EPOCH}},,%Y%m%d-%H%M%S)}}-${{CALLERID(num)}}-{tenant_id}-1010.wav,b)
 same => n,Dial(PJSIP/{tenant_id}-recepcao,20,g)
 same => n,GotoIf($["${{DIALSTATUS}}" = "ANSWER"]?pesquisa-satisfacao,s,1)
 same => n,Goto({tenant_id}-internal,1000,1)

exten => 1011,1,Answer()
 same => n,Playback(custom/aviso-gravacao)
 same => n,Set(CHANNEL(hangup_handler_push)=qualidade-chamada,s,1)
 same => n,MixMonitor(/var/spool/asterisk/monitor/${{STRFTIME(${{EPOCH}},,%Y%m%d-%H%M%S)}}-${{CALLERID(num)}}-{tenant_id}-1011.wav,b)
 same => n,Dial(PJSIP/{tenant_id}-recepcao-2,20,g)
 same => n,GotoIf($["${{DIALSTATUS}}" = "ANSWER"]?pesquisa-satisfacao,s,1)
 same => n,Goto({tenant_id}-internal,1000,1)

exten => 600,1,Answer()
 same => n,Echo()
 same => n,Hangup()

exten => *97,1,VoiceMailMain(${{CALLERID(num)}}@{tenant_id})
 same => n,Hangup()

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

; Ramais gerenciados pelo painel de administração (backlog #10/#38) -
; gerado pelo admin-api, não editar na mão.
#include extensions_dynamic_dial-{tenant_id}.conf

[{tenant_id}-hints]
exten => 1000,hint,PJSIP/{tenant_id}-recepcao&PJSIP/{tenant_id}-recepcao-2
exten => 1010,hint,PJSIP/{tenant_id}-recepcao
exten => 1011,hint,PJSIP/{tenant_id}-recepcao-2
#include extensions_dynamic_hints-{tenant_id}.conf
"""


def render_tenant_voicemail(tenant_id: str) -> str:
    return f"""{AUTO_GENERATED_HEADER}[{tenant_id}]
{tenant_id}-recepcao => 1234,{tenant_id.upper()} Recepcao Web 1
{tenant_id}-recepcao-2 => 1234,{tenant_id.upper()} Recepcao Web 2
#include voicemail_dynamic_{tenant_id}.conf
"""
