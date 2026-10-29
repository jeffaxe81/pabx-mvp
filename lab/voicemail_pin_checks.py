"""Verificador fail-closed de PINs do laboratório, sem expor segredos.

Verifica a configuração EFETIVAMENTE gerada no staging isolado para t1/t2/t3,
antes de inicializar Asterisk. Não verifica PIN digitado nem mensagens.
"""
import re

EXPECTED = {
    "t1": frozenset(("t1-1001", "t1-1002", "t1-recepcao", "t1-recepcao-2")),
    "t2": frozenset(("t2-1001", "t2-recepcao", "t2-recepcao-2")),
    "t3": frozenset(("t3-1001", "t3-recepcao", "t3-recepcao-2")),
}
PIN = re.compile(r"[1-9][0-9]{7}\Z")
KNOWN_WEAK = {"12345678", "87654321", "11223344", "12121212", "12341234", "87658765"}
TENANT = re.compile(r"t[1-9][0-9]*\Z")
MAILBOX = re.compile(r"t[1-9][0-9]*-[a-z0-9][a-z0-9_-]*\Z")


def validate_prepared_voicemail(*contents):
    """Somente contagens booleanas; nenhuma credencial no retorno."""
    found = {tenant: set() for tenant in EXPECTED}
    seen_pins = set()
    invalid = 0
    mailboxes = 0
    if len(contents) != 2 or any(not isinstance(v, str) or len(v) > 1024*1024 for v in contents):
        return {"ok": False, "mailboxes": 0, "invalid": 1}
    for content in contents:
        tenant = None
        for raw in content.splitlines():
            line = raw.strip()
            if not line or line.startswith((";", "#")):
                continue
            if line.startswith("["):
                match = re.fullmatch(r"\[([^\]]+)\]", line)
                if not match:
                    invalid += 1
                    tenant = None
                else:
                    section = match.group(1)
                    tenant = section if TENANT.fullmatch(section) else None
                continue
            if "=>" not in line:
                continue
            mailbox, fields = (part.strip() for part in line.split("=>", 1))
            mailboxes += 1
            pin = fields.split(",", 1)[0].strip()
            if (not MAILBOX.fullmatch(mailbox) or tenant not in EXPECTED
                    or mailbox not in EXPECTED[tenant] or mailbox in found[tenant]
                    or not PIN.fullmatch(pin) or pin in seen_pins
                    or len(set(pin)) < 3 or pin in KNOWN_WEAK):
                invalid += 1
                continue
            found[tenant].add(mailbox)
            seen_pins.add(pin)
    return {
        "ok": invalid == 0 and all(found[t] == names for t, names in EXPECTED.items()),
        "mailboxes": mailboxes,
        "invalid": invalid + sum(len(EXPECTED[t] - found[t]) for t in EXPECTED),
    }
