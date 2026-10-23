"""
Gera o CONTEÚDO dos 4 arquivos .conf dinâmicos a partir da lista de
ramais do painel. Lógica pura (recebe a lista, devolve string) -
escrever em disco é responsabilidade do server.py, não daqui, pra
manter isso 100% testável sem I/O.

Esses arquivos são incluídos (#include) nos .conf estáticos do
Asterisk - ver manual 16 pra como a inclusão funciona.
"""
import re

AUTO_GENERATED_HEADER = (
    "; ARQUIVO GERADO AUTOMATICAMENTE PELO PAINEL DE ADMINISTRAÇÃO.\n"
    "; NÃO EDITE NA MÃO - qualquer alteração aqui é sobrescrita na\n"
    "; próxima mudança feita pelo painel.\n\n"
)


def render_pjsip_dynamic(extensions: list) -> str:
    blocks = [AUTO_GENERATED_HEADER]
    for ext in extensions:
        name = ext["name"]
        tenant = ext.get("tenant", "t1")
        blocks.append(f"""[{name}](endpoint-secure)
context={tenant}-internal
subscribe_context={tenant}-hints
auth={name}
aors={name}
callerid={ext['display_name']} <{ext['number']}>
mailboxes={name}@{tenant}

[{name}]
type=auth
auth_type=userpass
username={name}
password={ext['password']}

[{name}]
type=aor
max_contacts=1
remove_existing=yes
""")
    return "\n".join(blocks)


def render_extensions_dynamic_dial(extensions: list) -> str:
    """Recebe já filtrado pra UM tenant - ver render_all()."""
    lines = [AUTO_GENERATED_HEADER]
    for ext in extensions:
        lines.append(
            f"exten => {ext['number']},1,MixMonitor(/var/spool/asterisk/monitor/"
            f"${{STRFTIME(${{EPOCH}},,%Y%m%d-%H%M%S)}}-${{CALLERID(num)}}-{ext['number']}.wav,b)\n"
            f" same => n,Set(CDR(accountcode)={ext['tenant']})\n"
            f" same => n,Dial(PJSIP/{ext['name']},20)\n"
            f" same => n,Hangup()\n"
        )
    return "\n".join(lines)


def render_extensions_dynamic_hints(extensions: list) -> str:
    """Recebe já filtrado pra UM tenant - ver render_all()."""
    lines = [AUTO_GENERATED_HEADER]
    for ext in extensions:
        lines.append(f"exten => {ext['number']},hint,PJSIP/{ext['name']}")
    return "\n".join(lines) + ("\n" if extensions else "")


def render_voicemail_dynamic(extensions: list) -> str:
    """Recebe já filtrado pra UM tenant - ver render_all()."""
    lines = [AUTO_GENERATED_HEADER]
    for ext in extensions:
        email = ext.get("email", "")
        # Compatibilidade: ramais anteriores à política de PIN aleatório
        # podem não ter voicemail_pin; exigem migração/rotação manual.
        pin = ext.get("voicemail_pin") or "1234"
        lines.append(f"{ext['name']} => {pin},{ext['display_name']},{email}")
    return "\n".join(lines) + ("\n" if extensions else "")


def render_all(extensions: list, tenant_ids=None) -> dict:
    """Gera um conjunto separado de dial/hints/voicemail por tenant.

    Sem tenant_ids preserva compatibilidade t1/t2. Quando informado,
    recebe somente IDs efetivamente provisionados; ramais órfãos e
    nomes malformados interrompem a geração em vez de vazarem para
    outro contexto ou produzirem paths arbitrários.
    """
    allowed = {"t1", "t2"} if tenant_ids is None else set(tenant_ids)
    if not allowed or any(
        not isinstance(tid, str)
        or not re.fullmatch(r"t[1-9][0-9]*", tid)
        for tid in allowed
    ):
        raise ValueError("lista de tenants provisionados inválida")

    by_tenant = {tid: [] for tid in allowed}
    for extension in extensions:
        tenant = extension.get("tenant", "t1")
        if tenant not in by_tenant:
            raise ValueError(f"ramal pertence a tenant não provisionado: {tenant}")
        by_tenant[tenant].append(extension)

    files = {"pjsip_dynamic.conf": render_pjsip_dynamic(extensions)}
    for tenant in sorted(allowed):
        tenant_extensions = by_tenant[tenant]
        files[f"extensions_dynamic_dial-{tenant}.conf"] = render_extensions_dynamic_dial(tenant_extensions)
        files[f"extensions_dynamic_hints-{tenant}.conf"] = render_extensions_dynamic_hints(tenant_extensions)
        files[f"voicemail_dynamic_{tenant}.conf"] = render_voicemail_dynamic(tenant_extensions)
    return files
