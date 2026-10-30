"""20 gates for generated tenant PJSIP/dialplan/queue/voicemail/parking.

A static *pre-publication* gate. It is not Asterisk runtime validation.
Never logs generated passwords or voicemail PINs.
"""
from pathlib import Path
import re

_TENANT = re.compile(r"t(?:[3-9]|[1-9][0-9]+)\Z")
MAX_FILE_SIZE_BYTES = 256 * 1024

CHECK_LABELS = (
    ("TP-01", "Tenant ID managed by wizard"),
    ("TP-02", "Exactly eight generated configuration files"),
    ("TP-03", "All expected paths reside in tenant config directories"),
    ("TP-04", "Every file is bounded, UTF-8 and has no CR/NUL"),
    ("TP-05", "Reception endpoint 1 uses expected tenant identity"),
    ("TP-06", "Reception endpoint 2 uses expected tenant identity"),
    ("TP-07", "Both endpoints are scoped to tenant dialplan context"),
    ("TP-08", "Each endpoint has its dedicated SIP auth"),
    ("TP-09", "Each endpoint has its dedicated AOR"),
    ("TP-10", "Both endpoints declare tenant-local voicemail mailbox"),
    ("TP-11", "General, English and Spanish queues exist"),
    ("TP-12", "General queue contains both tenant reception members"),
    ("TP-13", "Queue recording is enabled by MixMonitor"),
    ("TP-14", "Private internal and BLF contexts are generated"),
    ("TP-15", "Inbound reception uses tenant queue selector"),
    ("TP-16", "Cross-tenant mailbox access has explicit denial gate"),
    ("TP-17", "Tenant-specific outbound blocklist is used"),
    ("TP-18", "Dynamic dial/hint includes match tenant"),
    ("TP-19", "Three tenant-local voicemail boxes and include exist"),
    ("TP-20", "Call parking uses tenant context and isolated lot"),
)


def _expected_files(tenant):
    return {
        ("pjsip_tenants", tenant + ".conf"): "pjsip",
        ("queues_tenants", tenant + ".conf"): "queues",
        ("extensions_tenants", tenant + ".conf"): "extensions",
        ("voicemail_tenants", tenant + ".conf"): "voicemail",
        ("parking_tenants", tenant + ".conf"): "parking",
        ("generated", "extensions_dynamic_dial-" + tenant + ".conf"): "dynamic_dial",
        ("generated", "extensions_dynamic_hints-" + tenant + ".conf"): "dynamic_hints",
        ("generated", "voicemail_dynamic_" + tenant + ".conf"): "dynamic_voicemail",
    }


def inspect_generated_tenant_files(contents, tenant):
    """Returns fixed IDs and bool only, no secrets or generated content."""
    tid_ok = isinstance(tenant, str) and _TENANT.fullmatch(tenant) is not None
    expected = _expected_files(tenant) if tid_ok else {}
    valid_dict = isinstance(contents, dict)
    observed = {}
    if valid_dict:
        for path, content in contents.items():
            if not isinstance(path, (Path, str)):
                continue
            p = Path(path)
            observed[(p.parent.name, p.name)] = content
    texts = {name: observed.get(key, "") for key, name in expected.items()}
    p = texts.get("pjsip", "")
    q = texts.get("queues", "")
    x = texts.get("extensions", "")
    vm = texts.get("voicemail", "")
    park = texts.get("parking", "")
    safe_strings = valid_dict and all(
        isinstance(value, str)
        and len(value.encode("utf-8")) <= MAX_FILE_SIZE_BYTES
        and "\r" not in value and "\x00" not in value
        for value in contents.values()
    )
    if not safe_strings:
        p = q = x = vm = park = ""
    endpoints = [tenant + "-recepcao", tenant + "-recepcao-2"] if tid_ok else []
    checks = (
        tid_ok,
        valid_dict and len(contents) == 8,
        valid_dict and len(observed) == len(contents) and set(observed) == set(expected),
        safe_strings,
        tid_ok and ("[" + endpoints[0] + "](endpoint-webrtc)") in p,
        tid_ok and ("[" + endpoints[1] + "](endpoint-webrtc)") in p,
        tid_ok and p.count("context=" + tenant + "-internal") >= 2,
        tid_ok and all(("\nauth=" + name + "\n") in p and ("[" + name + "]\ntype=auth") in p
                       for name in endpoints),
        tid_ok and all(("\naors=" + name + "\n") in p and ("[" + name + "]\ntype=aor") in p
                       for name in endpoints),
        tid_ok and all(("mailboxes=" + name + "@" + tenant) in p for name in endpoints),
        tid_ok and all(("[" + name + "]") in q
                       for name in ("fila-" + tenant, "fila-" + tenant + "-en",
                                    "fila-" + tenant + "-es")),
        tid_ok and all(("\nmember => PJSIP/" + name + "\n") in q for name in endpoints),
        tid_ok and q.count("monitor-type = mixmonitor") >= 3,
        tid_ok and ("[" + tenant + "-internal]") in x
                       and ("[" + tenant + "-hints]") in x,
        tid_ok and ("Queue(${FILA_IDIOMA},c,,,") in x
                       and ("Set(TENANT=" + tenant + ")") in x,
        tid_ok and ("PJSIP_ENDPOINT(${VM_ENDPOINT},context)") in x
                       and ("voicemail-negado") in x,
        tid_ok and ("DB(blocklist-" + tenant + "/") in x,
        tid_ok and all(("#include generated/" + filename) in x
                       for filename in ("extensions_dynamic_dial-" + tenant + ".conf",
                                        "extensions_dynamic_hints-" + tenant + ".conf")),
        tid_ok and ("[" + tenant + "]") in vm
                       and all((name + " => ") in vm
                               for name in (tenant + "-1001", *endpoints))
                       and ("#include generated/voicemail_dynamic_" + tenant + ".conf") in vm,
        tid_ok and ("[parkinglot-" + tenant + "]") in park
                       and ("context = " + tenant + "-internal") in park
                       and "parkpos = 76-95" in park,
    )
    return [{"id": cid, "ok": bool(ok)} for (cid, _), ok in zip(CHECK_LABELS, checks)]


def validate_generated_tenant_files(contents, tenant):
    """Fail-closed before writing files or contacting AMI/AstDB."""
    checks = inspect_generated_tenant_files(contents, tenant)
    if len(checks) != 20 or any(not result["ok"] for result in checks):
        # Only control IDs; generated files may hold passwords/PINs.
        failed = ",".join(row["id"] for row in checks if not row["ok"])
        raise ValueError("tenant pre-publication validation failed: " + failed)
    return True
