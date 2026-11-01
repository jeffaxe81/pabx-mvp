"""REL-04: roteamento real do Asterisk com Dial substituído somente no sandbox.

O dialplan de saída t1/t2 é exercitado por canais Local/. No lugar do
envio externo, o Dial final é instrumentado para gravar PRIMARY/SECONDARY
na AstDB efêmera. Nenhuma chamada vai a tronco ou operadora.
"""
from pathlib import Path
import re
import time

FAMILY = "rel04-results"
CASES = (
    ("t1-int-block", "t1", "00012345678", "DENY"),
    ("t2-int-allow", "t2", "00012345678", "PRIMARY:0012345678"),
    ("t1-national", "t1", "01198765432", "PRIMARY:1198765432"),
    ("t1-int-allow", "t1", "00012345678", "SECONDARY:012345678"),
    ("t2-int-block", "t2", "00012345678", "DENY"),
    ("t1-after-t2-block", "t1", "00012345678", "SECONDARY:012345678"),
    ("t1-blocklist", "t1", "01198765432", "DENY"),
    ("t1-secondary-blocklist", "t1", "00012345678", "DENY"),
    ("t2-national", "t2", "01198765432", "PRIMARY:1198765432"),
)


def required_route_checks():
    return {"routes_contexts_loaded", "routes_private_dial_intercepted",
            "routes_tenant_policy_isolated"} | {
        "route_decision:" + case for case, _, _, _ in CASES
    }


def prepare_routes(prepared):
    conf = Path(prepared["conf"])
    original = conf / "extensions.conf"
    value = original.read_text(encoding="utf-8")
    primary = " same => n,Dial(PJSIP/${DESTINO}@gateway-tdm,30)"
    secondary = " same => n,Dial(PJSIP/${DESTINO}@gateway-tdm-2,30)"
    blocked = "exten => numero-bloqueado,1,NoOp(Chamada bloqueada pela regra de discagem: ${DESTINO})"
    if (value.count(primary), value.count(secondary), value.count(blocked)) != (2, 1, 2):
        raise ValueError("dialplan de saída não corresponde à versão revisada")
    value = value.replace(primary,
       " same => n,Set(DB(rel04-results/${REL04_KEY})=PRIMARY:${DESTINO})\n same => n,Hangup()")
    value = value.replace(secondary,
       " same => n,Set(DB(rel04-results/${REL04_KEY})=SECONDARY:${DESTINO})\n same => n,Hangup()")
    value = value.replace(blocked,
       "exten => numero-bloqueado,1,Set(DB(rel04-results/${REL04_KEY})=DENY)")
    fixture = conf / "generated" / "rel04_outbound.conf"
    body = []
    for case, tenant, dialed, _expected in CASES:
        body += [
            f"[lab-rel04-{case}]",
            "exten => s,1,Answer()",
            f" same => n,Set(REL04_KEY={case})",
            f" same => n,Goto({tenant}-internal,{dialed},1)",
            "",
        ]
    fixture.write_text("\n".join(body) + "\n", encoding="utf-8")
    fixture.chmod(0o600)
    original.write_text(value + "\n#include generated/rel04_outbound.conf\n", encoding="utf-8")
    original.chmod(0o600)


def exercise_routes(container, report):
    from .asterisk_lab import cli
    checks = report["checks"]
    checks.update({k: False for k in required_route_checks()})
    report["route_cases"] = {}
    for case, _, _, _ in CASES:
        if "lab-rel04-" + case not in cli(container, "dialplan show lab-rel04-" + case):
            raise RuntimeError("contexto REL-04 não carregado")
    checks["routes_contexts_loaded"] = True
    # Risco de chamada externa eliminado na cópia temporária, sem tocar nos arquivos do repositório.
    checks["routes_private_dial_intercepted"] = True
    cli(container, "database put politica-externa-t1 internacional bloquear")
    for case, _tenant, _dialed, expected in CASES:
        if case == "t1-int-allow":
            cli(container, "database del politica-externa-t1 internacional")
        if case == "t2-int-block":
            cli(container, "database put politica-externa-t2 internacional bloquear")
        if case == "t1-blocklist":
            cli(container, "database put blocklist-t1 1198765432 1")
        if case == "t1-secondary-blocklist":
            cli(container, "database put blocklist-t1 012345678 1")
        report["phase"] = "route:" + case
        cli(container, f"channel originate Local/s@lab-rel04-{case} application Wait 1")
        value = None
        for _ in range(30):
            state = cli(container, f"database get {FAMILY} {case}")
            result = re.search(r"(?m)^Value:\s*(DENY|PRIMARY:[0-9]+|SECONDARY:[0-9]+)\s*$", state)
            if result:
                value = result.group(1)
                break
            time.sleep(0.1)
        checks["route_decision:" + case] = value == expected
        report["route_cases"][case] = {"expected": expected, "observed": value,
                                        "pass": value == expected}
        if value != expected:
            # Apenas números e classificações SINTÉTICOS gerados neste teste.
            print("REL04_ROUTE_MISMATCH", case, "expected", expected, "observed", value, flush=True)
            raise RuntimeError("roteamento REL-04 divergente do esperado")
    checks["routes_tenant_policy_isolated"] = all(
        checks["route_decision:" + key] for key in (
            "t1-int-block", "t2-int-allow", "t2-int-block", "t1-after-t2-block"
        )
    )
    report["routes_prefix_and_astdb_tested"] = all(checks[k] for k in required_route_checks())
    report["external_operator_trunks_tested"] = False
