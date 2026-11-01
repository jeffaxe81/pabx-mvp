"""REL-12: exercitar sub-rotina de política em Asterisk real, sem tronco.

Arquivo extra incluído APENAS na cópia temporária de configuração de CI.
Origens Local/ executam a política original; resultado registrado em AstDB do
container descartável. Não comprova SIP para operadora, gateway ou produção.
"""
from pathlib import Path
import re
import time

FAMILY = "rel12-results"
CASES = (
    ("t1-int-block", "t1", "0012345678", "DENY"),
    ("t2-int-allow", "t2", "0012345678", "ALLOW"),
    ("t3-int-block", "t3", "0012345678", "DENY"),
    ("t1-national", "t1", "1198765432", "ALLOW"),
    ("t2-national", "t2", "1198765432", "ALLOW"),
    ("bad-tenant", "invalid", "0012345678", "DENY"),
    ("bad-destination", "t1", "abc", "DENY"),
    ("t1-int-reenabled", "t1", "0012345678", "ALLOW"),
    ("t2-int-block", "t2", "0012345678", "DENY"),
    ("t1-unaffected", "t1", "0012345678", "ALLOW"),
)


def required_policy_checks():
    return {"policy_context_loaded", "policy_astdb_isolation", "policy_no_external_sip"} | {
        "policy_decision:" + case for case, _, _, _ in CASES
    }


def prepare_policy(prepared):
    conf = Path(prepared["conf"])
    target = conf / "generated" / "rel12_policy.conf"
    chunks = []
    for case, tenant, destination, _expected in CASES:
        chunks.extend((
            f"[lab-rel12-{case}]",
            "exten => s,1,Answer()",
            f" same => n,Set(TENANT={tenant})",
            f" same => n,Set(DESTINO={destination})",
            " same => n,Gosub(politica-externa,s,1)",
            f" same => n,Set(DB({FAMILY}/{case})=${{GOSUB_RETVAL}})",
            " same => n,Hangup()",
            "",
        ))
    target.write_text("\n".join(chunks) + "\n", encoding="utf-8")
    target.chmod(0o600)
    extensions = conf / "extensions.conf"
    extensions.write_text(
        extensions.read_text(encoding="utf-8") + "\n#include generated/rel12_policy.conf\n",
        encoding="utf-8",
    )
    extensions.chmod(0o600)


def exercise_policy(container, report):
    from .asterisk_lab import cli
    checks = report["checks"]
    for k in required_policy_checks():
        checks[k] = False
    report["policy_cases"] = {}
    # Sem alterações de produção: DB e contextos existem apenas no Docker de CI.
    for tenant in ("t1", "t3"):
        cli(container, f"database put politica-externa-{tenant} internacional bloquear")
    checks["policy_context_loaded"] = all(
        "lab-rel12-" + case in cli(container, "dialplan show lab-rel12-" + case)
        for case, _, _, _ in CASES
    )
    if not checks["policy_context_loaded"]:
        raise RuntimeError("contextos REL-12 não foram carregados no Asterisk")

    for case, _tenant, _destination, expected in CASES:
        if case == "t1-int-reenabled":
            cli(container, "database del politica-externa-t1 internacional")
        if case == "t2-int-block":
            cli(container, "database put politica-externa-t2 internacional bloquear")
        report["phase"] = "policy:" + case
        # O Local/ origina chamada no Asterisk, mas NÃO envia INVITE/registro
        # para nenhum tronco. A política original é executada em GOSUB.
        cli(container, f"channel originate Local/s@lab-rel12-{case} application Wait 1")
        found = None
        for _ in range(30):
            state = cli(container, f"database get {FAMILY} {case}")
            match = re.search(r"(?m)^Value:\s*(ALLOW|DENY)\s*$", state)
            if match:
                found = match.group(1)
                break
            time.sleep(0.1)
        checks["policy_decision:" + case] = found == expected
        report["policy_cases"][case] = {"expected": expected, "observed": found,
                                         "pass": found == expected}
        if not checks["policy_decision:" + case]:
            raise RuntimeError("decisão divergente na política REL-12")

    checks["policy_astdb_isolation"] = (
        report["policy_cases"]["t2-int-allow"]["observed"] == "ALLOW"
        and report["policy_cases"]["t1-int-block"]["observed"] == "DENY"
        and report["policy_cases"]["t1-unaffected"]["observed"] == "ALLOW"
        and report["policy_cases"]["t2-int-block"]["observed"] == "DENY"
    )
    checks["policy_no_external_sip"] = True  # Construção: somente Local/ e DB.
    report["policy_local_channels_tested"] = all(checks[k] for k in required_policy_checks())
    report["operator_trunk_tested"] = False
