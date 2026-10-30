#!/usr/bin/env python3
"""Registra pendências sem executar provas ou autorizar GO.

Código pode ser integrado e considerado para homologação controlada em
ambiente real. Sem evidência, seu status é registrado como implementação
pendente de homologação; a aprovação definitiva depende de aceite separado.
Esta ferramenta não acessa telefonia ou infraestrutura operacional.
"""
import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTER = ROOT / "docs/quality/provas-operacionais-diferidas.json"
DEFAULT_PLAN = ROOT / "docs/plano-16-semanas-pabx.json"
MAX_SIZE = 1024 * 1024
ID = re.compile(r"PABX-OPS-(?:0[8-9]|1[0-6])-[A-Z0-9-]{2,40}\Z")


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON com chaves duplicadas")
        result[key] = value
    return result


def read_json(path):
    file = Path(path)
    if file.is_symlink() or not file.is_file() or file.stat().st_size > MAX_SIZE:
        raise ValueError("arquivo ausente, simbólico ou grande demais")
    return json.loads(file.read_text(encoding="utf-8"), object_pairs_hook=unique_keys,
                      parse_constant=lambda _: (_ for _ in ()).throw(
                          ValueError("numero JSON nao finito")))


def summarize(registry, plan):
    if not isinstance(registry, dict) or not isinstance(plan, dict):
        raise ValueError("registro e plano devem ser objetos")
    if registry.get("schema_version") != 1 or registry.get("project") != "AXE PABX":
        raise ValueError("registro nao pertence ao programa AXE PABX")
    when = registry.get("registered_on")
    if not isinstance(when, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", when):
        raise ValueError("data de registro invalida")
    try:
        date.fromisoformat(when)
    except ValueError as exc:
        raise ValueError("data de registro invalida") from exc
    if registry.get("execution_mode") != "DEVELOPMENT_ONLY_PROOFS_DEFERRED":
        raise ValueError("modo operacional diferente do solicitado")
    real_policy = registry.get("real_environment_policy")
    if not isinstance(real_policy, dict):
        raise ValueError("politica de homologacao em ambiente real ausente")
    expected_policy = {
        "controlled_application_allowed_for_homologation": True,
        "unproven_code_status": "CODE_REGISTERED_PENDING_REAL_HOMOLOGATION",
        "record_missing_evidence_without_claiming_approval": True,
        "automated_code_and_security_ci_required": True,
        "target_environment_preflight_and_rollback_required": True,
        "production_go_requires_separate_explicit_acceptance": True,
    }
    if real_policy != expected_policy:
        raise ValueError("politica de uso real e homologacao inconsistente")
    for flag, desired in (
        ("operational_proofs_executed_in_this_change", False),
        ("operational_go_authorized", False),
        ("ci_security_gates_must_remain_enabled", True),
    ):
        if registry.get(flag) is not desired:
            raise ValueError("politica de homologacao inconsistente")
    if (plan.get("schema_version") != 1 or plan.get("project") != "AXE PABX"
            or plan.get("operational_go_authorized") is not False):
        raise ValueError("plano invalido ou autorizacao de GO indevida")
    plan_policy = plan.get("development_policy")
    if not isinstance(plan_policy, dict) or any(
        plan_policy.get(name) != expected
        for name, expected in (
            ("controlled_real_environment_homologation_permitted", True),
            ("unproven_implementation_code_status", "CODE_REGISTERED_PENDING_REAL_HOMOLOGATION"),
            ("real_environment_validation_requires_target_checks_and_rollback", True),
            ("homologation_and_final_production_go_are_separate_decisions", True),
        )
    ):
        raise ValueError("plano nao corresponde a politica de homologacao real")
    milestones = plan.get("milestones")
    if not isinstance(milestones, list) or len(milestones) != 16:
        raise ValueError("plano precisa dos 16 marcos")
    by_week = {}
    for row in milestones:
        if not isinstance(row, dict) or type(row.get("week")) is not int:
            raise ValueError("marco malformado")
        if row["week"] in by_week:
            raise ValueError("marco repetido")
        by_week[row["week"]] = row
    if set(by_week) != set(range(1, 17)):
        raise ValueError("faltam marcos do programa")
    checks = registry.get("pending_checks")
    if not isinstance(checks, list) or not checks:
        raise ValueError("nenhuma pendencia registrada")
    ids = set()
    affected = set()
    for row in checks:
        if not isinstance(row, dict):
            raise ValueError("pendencia malformada")
        check_id, week = row.get("id"), row.get("milestone_week")
        if (not isinstance(check_id, str) or not ID.fullmatch(check_id)
                or check_id in ids or type(week) is not int or week not in by_week
                or not check_id.startswith(f"PABX-OPS-{week:02d}-")):
            raise ValueError("ID de prova repetido, ausente ou inconsistente")
        ids.add(check_id)
        affected.add(week)
        if by_week[week].get("status") == "done":
            raise ValueError("marco dado como concluido apesar de prova pendente")
        if row.get("status") != "DEFERRED_NOT_EXECUTED":
            raise ValueError("pendencia alterada para estado nao executado sem aceite")
        if row.get("homologation_required") is not True or row.get("target_environment") != "REAL_ENVIRONMENT":
            raise ValueError("pendencia sem homologacao real obrigatoria")
        if not isinstance(row.get("description"), str) or not 15 <= len(row["description"]) <= 500:
            raise ValueError("descricao ausente ou excessiva")
        if any(ord(c) < 32 or ord(c) == 127 for c in row["description"]):
            raise ValueError("descricao possui caracteres de controle")
        if any(row.get(k) is not None for k in ("evidence", "executed_at", "approved_at")):
            raise ValueError("registro diferido nao pode alegar evidencia ou execucao")
        if type(row.get("tracking_issue")) is not int or row["tracking_issue"] < 1:
            raise ValueError("pendencia sem rastreabilidade")
    formal = sum(row.get("status") == "done" for row in milestones)
    return {
        "project": "AXE PABX",
        "mode": registry["execution_mode"],
        "registered_pending_checks": len(checks),
        "affected_milestones": sorted(affected),
        "executed_operational_proofs": 0,
        "formal_milestones_done": formal,
        "formal_milestones_total": 16,
        "formal_percent": round(formal * 100 / 16, 1),
        "development_can_continue": True,
        "controlled_real_environment_homologation_allowed": True,
        "unproven_code_status": real_policy["unproven_code_status"],
        "pending_real_environment_homologations": len(checks),
        "target_preflight_and_rollback_required": True,
        "automated_ci_still_required": True,
        "homologation_complete": False,
        "operational_go_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    args = parser.parse_args(argv)
    try:
        report = summarize(read_json(args.register), read_json(args.plan))
    except (ValueError, TypeError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print("Registro de provas operacionais invalido: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
