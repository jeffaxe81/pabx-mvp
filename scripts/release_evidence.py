#!/usr/bin/env python3
"""Vincula auditoria CLI e homologação declarada ao mesmo SHA de release.

Nunca transforma registros declarados em prova verificada e NÃO autoriza GO.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from homologation_gate import summarize as summarize_homologation

SHA_RE = re.compile(r"[0-9a-fA-F]{40}\Z")
MAX_EVIDENCE_BYTES = 1024 * 1024


def read_report(path):
    location = Path(path)
    if location.is_symlink() or not location.is_file():
        raise ValueError("arquivo de evidência ausente ou inseguro")
    if location.stat().st_size > MAX_EVIDENCE_BYTES:
        raise ValueError("arquivo de evidência acima do limite")
    raw = location.read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("arquivo de evidência não é JSON UTF-8") from exc
    return payload, hashlib.sha256(raw).hexdigest()


def validate_lab_audit(report, expected_sha):
    if not isinstance(report, dict):
        raise ValueError("auditoria deve ser objeto")
    if report.get("schema_version") != 1 or report.get("kind") != "running_asterisk_readonly_lab_audit":
        raise ValueError("tipo de auditoria inválido")
    sha = report.get("source_commit")
    if not isinstance(sha, str) or not SHA_RE.fullmatch(sha) or sha.lower() != expected_sha:
        raise ValueError("auditoria não corresponde ao SHA do release")
    if report.get("source_commit_verified_by_this_tool") is not False:
        raise ValueError("campo de verificação de commit inválido")

    checks = report.get("checks")
    if not isinstance(checks, dict) or not checks or not all(
        isinstance(k, str) and len(k) <= 100 and type(v) is bool
        for k, v in checks.items()
    ):
        raise ValueError("checks da auditoria inválidos")
    required = {
        "runtime_version", "transport:transport-tls", "transport:transport-wss",
        "ingress_unknown_did_rejection",
        "endpoint_exists:t1", "endpoint_exists:t2",
        "endpoint_context:t1", "endpoint_context:t2",
        "dialplan_context:t1", "dialplan_context:t2",
    }
    if not required.issubset(checks):
        raise ValueError("auditoria não cobre os controles básicos")
    passed = sum(checks.values())
    if type(report.get("passed")) is not int or report["passed"] != passed:
        raise ValueError("contagem inconsistente de checks")
    if type(report.get("total")) is not int or report["total"] != len(checks):
        raise ValueError("total de checks inconsistente")
    if type(report.get("ready_for_call_homologation")) is not bool or (
        report["ready_for_call_homologation"] != (passed == len(checks))
    ):
        raise ValueError("indicador de auditoria inconsistente")
    for flag in ("registration_verified", "sip_call_tested", "rtp_tested",
                 "srtp_tested", "live_tenant_isolation_tested", "backup_restore_tested"):
        if report.get(flag) is not False:
            raise ValueError("auditoria somente leitura não comprova ensaios reais")
    return {"passed": passed, "total": len(checks),
            "ready": report["ready_for_call_homologation"]}


def compile_release_report(expected_sha, lab, homologation, lab_digest, homologation_digest):
    if not isinstance(expected_sha, str) or not SHA_RE.fullmatch(expected_sha):
        raise ValueError("SHA de release inválido")
    sha = expected_sha.lower()
    audit = validate_lab_audit(lab, sha)
    gate = summarize_homologation(homologation)
    if gate["source_commit"] != sha:
        raise ValueError("homologação não corresponde ao SHA de release")
    review_ready = audit["ready"] and gate["gate_ready"]
    return {
        "schema_version": 1,
        "kind": "release_evidence_review",
        "source_commit": sha,
        "lab_checks_passed": audit["passed"],
        "lab_checks_total": audit["total"],
        "human_scenarios_passed": gate["counts"]["passed"],
        "human_scenarios_total": gate["total"],
        "declared_scenario_coverage_percent": gate["coverage_percent"],
        "review_ready": review_ready,
        "decision": "APTO PARA REVISÃO HUMANA DE GO" if review_ready else "BLOQUEADO",
        "artifact_sha256": {
            "lab_audit": lab_digest, "homologation": homologation_digest,
        },
        "artifact_authenticity_checked": False,
        "source_commit_verified_against_deployment": False,
        "real_calls_executed_by_this_tool": False,
        "operational_go_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True, help="SHA completo do release avaliado")
    parser.add_argument("--lab-audit", required=True, help="JSON da auditoria de Asterisk")
    parser.add_argument("--homologation", required=True, help="JSON do Manual 73")
    args = parser.parse_args(argv)
    try:
        lab, lab_hash = read_report(args.lab_audit)
        homol, homol_hash = read_report(args.homologation)
        report = compile_release_report(args.sha, lab, homol, lab_hash, homol_hash)
    except (OSError, ValueError) as exc:
        print(f"Evidências de release inválidas: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["review_ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
