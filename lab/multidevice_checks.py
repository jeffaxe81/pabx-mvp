"""Prova de até 3 registros PJSIP/TLS simultâneos por ramal dinâmico.

O laboratório gera novos ramais com senhas aleatórias exclusivamente no
Asterisk descartável, sem tocar na configuração original. Prova contatos,
não garante qualidade de mídia, políticas de atendimento nem deploy.
"""
from contextlib import ExitStack
from pathlib import Path
import secrets
import time

CASES = (("t1", 1), ("t2", 2), ("t3", 3))


def required_multidevice_checks():
    return {
        f"multidevice_generated:{tenant}" for tenant, _ in CASES
    } | {
        f"multidevice_registered:{tenant}" for tenant, _ in CASES
    } | {
        f"multidevice_count:{tenant}" for tenant, _ in CASES
    } | {
        "multidevice_fourth_bounded:t3",
        "multidevice_no_foreign_context",
    }


def prepare_multidevice(prepared):
    from .asterisk_lab import load_file
    root = Path(__file__).resolve().parents[1]
    generator = load_file("multidevice_conf_generator", root / "admin-api" / "conf_generator.py")
    credentials = {}
    extensions = []
    for tenant, limit in CASES:
        endpoint = tenant + "-multi"
        secret = secrets.token_urlsafe(24)
        credentials[endpoint] = secret
        extensions.append({
            "name": endpoint, "number": 1150,
            "display_name": "SIP Lab " + tenant,
            "password": secret, "tenant": tenant,
            "email": "", "voicemail_pin": str(secrets.randbelow(90_000_000) + 10_000_000),
            "max_contacts": limit,
        })
    generated = generator.render_all(extensions, tenant_ids={"t1", "t2", "t3"})
    for path, body in generated.items():
        target = prepared["conf"] / "generated" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        target.chmod(0o600)
    prepared["multidevice_credentials"] = credentials
    prepared["multidevice_expected"] = {tenant: count for tenant, count in CASES}


def _contact_count(container, endpoint):
    from .asterisk_lab import cli
    text = cli(container, "pjsip show contacts")
    # O CLI apresenta cada contato da AOR como "endpoint/sip:...".
    return sum(endpoint + "/" in line for line in text.splitlines())


def _wait_equal(container, endpoint, count, duration=7):
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        if _contact_count(container, endpoint) == count:
            return True
        time.sleep(.16)
    return _contact_count(container, endpoint) == count


def exercise_multidevice(container, prepared, report):
    from .asterisk_lab import cli
    from .sip_tls import SipTLS

    checks = report["checks"]
    checks.update({key: False for key in required_multidevice_checks()})
    report["phase"] = "multidevice_sip_tls"
    contexts_ok = True
    for tenant, expected in CASES:
        endpoint = tenant + "-multi"
        report["phase"] = "multidevice:" + tenant
        context = cli(container, "pjsip show endpoint " + endpoint)
        checks[f"multidevice_generated:{tenant}"] = (
            "context" in context.lower() and tenant + "-internal" in context
            and _contact_count(container, endpoint) == 0
        )
        contexts_ok &= checks[f"multidevice_generated:{tenant}"]
        with ExitStack() as stack:
            clients = []
            for number in range(expected):
                client = SipTLS(
                    "127.0.0.1", 5061, prepared["ca"], endpoint,
                    prepared["multidevice_credentials"][endpoint],
                )
                stack.callback(client.close)
                clients.append(client)
                if client.register() != 200:
                    break
            checks[f"multidevice_registered:{tenant}"] = len(clients) == expected
            checks[f"multidevice_count:{tenant}"] = _wait_equal(
                container, endpoint, expected)
            # Um quarto REGISTER não pode manter quatro contatos, mesmo
            # se remove_existing=yes substituir automaticamente o mais antigo.
            if expected == 3:
                client = SipTLS(
                    "127.0.0.1", 5061, prepared["ca"], endpoint,
                    prepared["multidevice_credentials"][endpoint],
                )
                stack.callback(client.close)
                result = client.register()
                deadline = time.monotonic() + 7
                while time.monotonic() < deadline and _contact_count(container, endpoint) > 3:
                    time.sleep(.15)
                checks["multidevice_fourth_bounded:t3"] = (
                    result in (200, 403, 480)
                    and _contact_count(container, endpoint) <= 3
                )
    checks["multidevice_no_foreign_context"] = contexts_ok
    report["multidevice_sip_registration_tested"] = all(
        checks[k] for k in required_multidevice_checks()
    )
    report["multidevice_media_or_production_certified"] = False
