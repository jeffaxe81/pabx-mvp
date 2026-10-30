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
    validate_dynamic_extensions(normalized, allowed, files)
    return files


# Validação incorporada ao gerador: o laboratório SIP extrai este módulo
# isoladamente para um diretório temporário e não copia dependências extras.
"""30 prepublication invariants for dynamic Asterisk extension configurations.

Called by render_all after persisted-extension validation. This independent
gate checks consistency across PJSIP, dialplan, BLF hints and voicemail.
Results and errors NEVER return PINs, SIP passwords, customer data or names.
This is static analysis, not an Asterisk runtime proof.
"""
import re

MAX_GENERATED_CONF_BYTES = 2 * 1024 * 1024
_TENANT_RE = re.compile(r"t[1-9][0-9]*\Z")
_RULE_DESCRIPTIONS = (
    "valid provisioned tenant IDs",
    "unique dynamic endpoint names",
    "unique extension numbers inside each tenant",
    "expected number of generated files",
    "exact generated file names",
    "generated files are text",
    "generated files contain no CR/NUL",
    "generated files within 2 MiB each",
    "every file includes generation banner",
    "all expected PJSIP endpoint blocks exist once",
    "no unknown PJSIP endpoint blocks",
    "endpoint context belongs to its tenant",
    "subscription context belongs to its tenant",
    "endpoint references its own auth",
    "endpoint references its own AOR",
    "endpoint caller ID matches extension number and display",
    "endpoint voicemail belongs to its tenant",
    "SIP auth block is present once",
    "SIP auth username matches the endpoint",
    "SIP auth secret matches the persisted record",
    "SIP AOR block is present once",
    "SIP AOR permits exactly one contact",
    "SIP AOR removes previous registration",
    "exact dynamic dialed extension numbers",
    "per-extension MixMonitor enabled",
    "per-extension CDR accountcode belongs to its tenant",
    "per-extension Dial targets its own PJSIP endpoint",
    "per-extension Hangup is present",
    "BLF hint entries exactly match tenant extensions",
    "voicemail entries match tenant PIN, display and email",
)
RULES = tuple((f"DE-{i:02d}", desc) for i, desc in enumerate(_RULE_DESCRIPTIONS, 1))


def _sections(text):
    """Split PJSIP stanzas at exact blank-line boundaries."""
    if not isinstance(text, str):
        return []
    return [block.strip("\n").splitlines() for block in text.split("\n\n")
            if block.strip("\n").startswith("[")]


def _one(sections, heading, kind=None):
    matches = []
    for lines in sections:
        if not lines or lines[0] != heading:
            continue
        if kind is not None and f"type={kind}" not in lines:
            continue
        matches.append(lines)
    return matches[0] if len(matches) == 1 else []


def _dial_chunk(text, number):
    if not isinstance(text, str):
        return ""
    prefix = f"exten => {number},1,"
    matches = [entry.strip("\n") for entry in text.split("\n\n")
               if entry.strip("\n").startswith(prefix)]
    return matches[0] if len(matches) == 1 else ""


def inspect_dynamic_extensions(records, tenants, files):
    """Exactly thirty read-only checks over a fully rendered configuration."""
    valid_tenants = (
        isinstance(tenants, (set, frozenset, tuple, list))
        and bool(tenants)
        and all(isinstance(t, str) and _TENANT_RE.fullmatch(t) for t in tenants)
    )
    scoped = list(tenants) if valid_tenants else []
    valid_records = isinstance(records, list) and all(isinstance(x, dict) for x in records)
    rows = records if valid_records else []
    names = [e.get("name") for e in rows]
    numbers = [(e.get("tenant"), str(e.get("number"))) for e in rows]
    record_ok = all(
        isinstance(e.get("name"), str)
        and isinstance(e.get("tenant"), str)
        and isinstance(e.get("number"), (int, str))
        and not isinstance(e.get("number"), bool)
        for e in rows
    )
    expected_names = {"pjsip_dynamic.conf"}
    for t in scoped:
        expected_names.update({
            f"extensions_dynamic_dial-{t}.conf",
            f"extensions_dynamic_hints-{t}.conf",
            f"voicemail_dynamic_{t}.conf",
        })
    is_map = isinstance(files, dict)
    safe_map = files if is_map else {}
    texts_ok = all(isinstance(k, str) and isinstance(v, str)
                   for k, v in safe_map.items())
    no_controls = texts_ok and all("\r" not in v and "\x00" not in v
                                   for v in safe_map.values())
    bounded = texts_ok and all(
        len(v.encode("utf-8")) <= MAX_GENERATED_CONF_BYTES
        for v in safe_map.values()
    )
    banner = texts_ok and all(
        v.startswith("; ARQUIVO GERADO AUTOMATICAMENTE PELO PAINEL DE ADMINISTRAÇÃO.")
        for v in safe_map.values()
    )
    pjsip = safe_map.get("pjsip_dynamic.conf", "")
    pjsip_sections = _sections(pjsip)
    expected_headers = {f"[{e.get('name')}](endpoint-secure)" for e in rows}
    actual_headers = [s[0] for s in pjsip_sections if s[0].endswith("](endpoint-secure)")]
    endpoints = [_one(pjsip_sections, f"[{e['name']}](endpoint-secure)")
                 for e in rows if record_ok]
    auth_blocks = [_one(pjsip_sections, f"[{e['name']}]", "auth")
                   for e in rows if record_ok]
    aor_blocks = [_one(pjsip_sections, f"[{e['name']}]", "aor")
                  for e in rows if record_ok]
    def matches_field(blocks, function):
        return record_ok and len(blocks) == len(rows) and all(
            function(row, lines) for row, lines in zip(rows, blocks)
        )
    def endpoint_field(e, lines, field):
        return lines.count(field) == 1
    def get_dial(e):
        return _dial_chunk(safe_map.get(
            f"extensions_dynamic_dial-{e['tenant']}.conf", ""), e["number"])
    dial_chunks = [get_dial(e) for e in rows] if record_ok else []
    expected_dial = {
        t: [str(e["number"]) for e in rows if e.get("tenant") == t]
        for t in scoped
    }
    actual_dial = {}
    for t in scoped:
        txt = safe_map.get(f"extensions_dynamic_dial-{t}.conf", "")
        actual_dial[t] = re.findall(r"(?m)^exten => ([0-9]{4}),1,", txt) if isinstance(txt, str) else []
    def dial_matches(e, chunk, token):
        return isinstance(chunk, str) and bool(chunk) and token in chunk
    hints_exact = True
    voicemail_exact = True
    for t in scoped:
        hints = safe_map.get(f"extensions_dynamic_hints-{t}.conf", "")
        vm = safe_map.get(f"voicemail_dynamic_{t}.conf", "")
        if not isinstance(hints, str) or not isinstance(vm, str):
            hints_exact = voicemail_exact = False
            continue
        actual_hints = [line for line in hints.splitlines() if line.startswith("exten => ")]
        expected_hints = [
            f"exten => {e['number']},hint,PJSIP/{e['name']}"
            for e in rows if e.get("tenant") == t
        ]
        if sorted(actual_hints) != sorted(expected_hints):
            hints_exact = False
        actual_vm = [line for line in vm.splitlines() if " => " in line and not line.startswith(";")]
        expected_vm = [
            f"{e['name']} => {e['voicemail_pin']},{e['display_name']},{e.get('email', '')}"
            for e in rows if e.get("tenant") == t
        ] if all("voicemail_pin" in e and "display_name" in e for e in rows) else []
        if sorted(actual_vm) != sorted(expected_vm):
            voicemail_exact = False

    flags = (
        bool(valid_tenants) and len(set(scoped)) == len(scoped),
        record_ok and len(names) == len(set(names)),
        record_ok and len(numbers) == len(set(numbers)),
        bool(is_map) and len(safe_map) == 1 + 3 * len(scoped),
        bool(is_map) and set(safe_map) == expected_names,
        texts_ok,
        no_controls,
        bounded,
        banner,
        record_ok and len(endpoints) == len(rows) and all(bool(e) for e in endpoints),
        record_ok and sorted(actual_headers) == sorted(expected_headers),
        matches_field(endpoints, lambda e, s: endpoint_field(s, s, f"context={e['tenant']}-internal")),
        matches_field(endpoints, lambda e, s: endpoint_field(s, s, f"subscribe_context={e['tenant']}-hints")),
        matches_field(endpoints, lambda e, s: endpoint_field(s, s, f"auth={e['name']}")),
        matches_field(endpoints, lambda e, s: endpoint_field(s, s, f"aors={e['name']}")),
        matches_field(endpoints, lambda e, s: endpoint_field(s, s, f"callerid={e['display_name']} <{e['number']}>")),
        matches_field(endpoints, lambda e, s: endpoint_field(s, s, f"mailboxes={e['name']}@{e['tenant']}")),
        record_ok and len(auth_blocks) == len(rows) and all(bool(x) for x in auth_blocks),
        matches_field(auth_blocks, lambda e, s: s.count(f"username={e['name']}") == 1),
        matches_field(auth_blocks, lambda e, s: s.count(f"password={e['password']}") == 1),
        record_ok and len(aor_blocks) == len(rows) and all(bool(x) for x in aor_blocks),
        matches_field(aor_blocks, lambda e, s: s.count("max_contacts=1") == 1),
        matches_field(aor_blocks, lambda e, s: s.count("remove_existing=yes") == 1),
        record_ok and all(sorted(actual_dial[t]) == sorted(expected_dial[t]) for t in scoped),
        record_ok and all(dial_matches(e, chunk, "MixMonitor(/var/spool/asterisk/monitor/")
                          for e, chunk in zip(rows, dial_chunks)),
        record_ok and all(dial_matches(e, chunk, f" same => n,Set(CDR(accountcode)={e['tenant']})")
                          for e, chunk in zip(rows, dial_chunks)),
        record_ok and all(dial_matches(e, chunk, f" same => n,Dial(PJSIP/{e['name']},20)")
                          for e, chunk in zip(rows, dial_chunks)),
        record_ok and all(chunk.rstrip().endswith("same => n,Hangup()")
                          for chunk in dial_chunks),
        record_ok and hints_exact,
        record_ok and voicemail_exact,
    )
    if len(flags) != 30:
        raise RuntimeError("incomplete dynamic extension check list")
    return [{"id": rule_id, "ok": bool(passed)}
            for (rule_id, _), passed in zip(RULES, flags)]


def validate_dynamic_extensions(records, tenants, files):
    """Fail closed with fixed check IDs, never interpolate SIP passwords."""
    checks = inspect_dynamic_extensions(records, tenants, files)
    failed = [x["id"] for x in checks if not x["ok"]]
    if failed:
        raise ValueError("dynamic extension publication rejected: " + ",".join(failed))
    return True
