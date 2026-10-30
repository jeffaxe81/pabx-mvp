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
