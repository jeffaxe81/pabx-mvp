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
        # Um cadastro legado sem PIN próprio nunca deve produzir uma
        # mailbox com senha compartilhada. Migração exige ação autorizada.
        pin = ext.get("voicemail_pin")
        if not isinstance(pin, str) or not re.fullmatch(r"[1-9][0-9]{7}", pin):
            raise ValueError("PIN de voicemail ausente ou inválido; migração obrigatória")
        lines.append(f"{ext['name']} => {pin},{ext['display_name']},{email}")
    return "\n".join(lines) + ("\n" if extensions else "")



# Ultima barreira antes de publicar configuracoes geradas a partir de
# extensions_store.json. A validacao de HTTP nao protege o arquivo em disco
# contra corrupcao, restauracao antiga nem edicao fora do painel.
_NAME = re.compile(r"[a-z0-9-]{3,40}\Z")
_ENDPOINT_OWNER = re.compile(r"(t[1-9][0-9]*)-.+\Z")
_PASSWORD = re.compile(r"[A-Za-z0-9._~!@#$%^&*()+\-=]{1,128}\Z")
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}\Z")
_VOICEMAIL_PIN = re.compile(r"[1-9][0-9]{7}\Z")
_STATIC_ENDPOINTS = frozenset({
    "t1-1001", "t1-1002", "t1-recepcao", "t1-recepcao-2",
    "t2-1001", "t2-recepcao", "t2-recepcao-2",
})


def validate_persisted_extensions(extensions: list, tenant_ids: set) -> None:
    """Rejeita estado adulterado antes de qualquer arquivo/AMI ser atualizado.

    Compatibilidade: nome sem prefixo de tenant, PIN 1234 legado e
    passwords legados continuam legiveis, sem criacao automatica de segredo.
    """
    if not isinstance(extensions, list):
        raise ValueError("cadastro de ramais invalido")
    names, extensions_by_tenant = set(), set()
    for ext in extensions:
        if not isinstance(ext, dict):
            raise ValueError("registro de ramal invalido")
        tenant = ext.get("tenant", "t1")
        if not isinstance(tenant, str) or tenant not in tenant_ids:
            raise ValueError("ramal pertence a tenant não provisionado")
        name = ext.get("name")
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise ValueError("identificador de ramal invalido")
        owner = _ENDPOINT_OWNER.fullmatch(name)
        if owner and owner.group(1) != tenant:
            raise ValueError("identificador de endpoint pertence a outro tenant")
        if name in _STATIC_ENDPOINTS or name in {
            tenant + "-recepcao", tenant + "-recepcao-2"
        }:
            raise ValueError("identificador de endpoint reservado")
        if name in names:
            raise ValueError("identificador de endpoint duplicado")
        names.add(name)

        number = ext.get("number")
        if type(number) is int:
            number_ok = 1100 <= number <= 1199
            parsed_number = number
        elif (isinstance(number, str) and number.isascii()
              and number.isdecimal() and len(number) == 4):
            parsed_number = int(number)
            number_ok = 1100 <= parsed_number <= 1199
        else:
            number_ok, parsed_number = False, -1
        # O painel só cria 1100-1199. O laboratório usa números 1001
        # e 1002 em t2/t3 para provar as chamadas reais, sem usurpar
        # endpoints numéricos já existentes nos contextos estáticos.
        if (not number_ok and parsed_number in (1001, 1002)):
            number_ok = (
                tenant not in ("t1", "t2")
                or (tenant == "t2" and parsed_number == 1002)
            )
        if not number_ok:
            raise ValueError("numero de ramal invalido")
        if (tenant, parsed_number) in extensions_by_tenant:
            raise ValueError("numero repetido dentro do tenant")
        extensions_by_tenant.add((tenant, parsed_number))

        display = ext.get("display_name")
        if not isinstance(display, str) or not (
            1 <= len(display) <= 60 and display.isprintable()
        ) or any(ch in ";=,<>[]" for ch in display):
            raise ValueError("nome de exibicao do ramal invalido")
        password = ext.get("password")
        if not isinstance(password, str) or not _PASSWORD.fullmatch(password):
            raise ValueError("credencial SIP do ramal invalida")
        email = ext.get("email", "")
        if (not isinstance(email, str) or len(email) > 254
                or (email and not _EMAIL.fullmatch(email))):
            raise ValueError("email do voicemail invalido")
        pin = ext.get("voicemail_pin")
        if not isinstance(pin, str) or not _VOICEMAIL_PIN.fullmatch(pin):
            raise ValueError("PIN de voicemail persistido ausente ou invalido")

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

    validate_persisted_extensions(extensions, allowed)

    by_tenant = {tid: [] for tid in allowed}
    normalized = []
    for extension in extensions:
        tenant = extension.get("tenant", "t1")
        # O legado sem chave 'tenant' pertence a t1. Cópia evita
        # alterar snapshot do cadastro durante publicação de arquivos.
        ready = {**extension, "tenant": tenant}
        by_tenant[tenant].append(ready)
        normalized.append(ready)

    files = {"pjsip_dynamic.conf": render_pjsip_dynamic(normalized)}
    for tenant in sorted(allowed):
        tenant_extensions = by_tenant[tenant]
        files[f"extensions_dynamic_dial-{tenant}.conf"] = render_extensions_dynamic_dial(tenant_extensions)
        files[f"extensions_dynamic_hints-{tenant}.conf"] = render_extensions_dynamic_hints(tenant_extensions)
        files[f"voicemail_dynamic_{tenant}.conf"] = render_voicemail_dynamic(tenant_extensions)
    # Publicação segura: todas as relações cruzadas de ramais precisam
    # passar pela checagem, mesmo após a validação do cadastro JSON.
    from dynamic_extension_invariants import validate_dynamic_extensions
    validate_dynamic_extensions(normalized, allowed, files)
    return files
