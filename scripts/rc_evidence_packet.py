#!/usr/bin/env python3
"""Pacote offline de evidencias operacionais do AXE PABX.

Gera um modelo local para 13 cenarios e 15 provas e valida SOMENTE as
declaracoes registradas. Nao abre rede, nao executa telefonia, nao faz deploy
e NUNCA autoriza producao. Um resultado completo exige revisao humana externa.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys

from homologation_gate import SCENARIOS, summarize as summarize_homologation

ROOT = Path(__file__).resolve().parents[1]
OPS_FILE = "docs/quality/provas-operacionais-diferidas.json"
HOMOLOG_FILE = "docs/modelo-homologacao-pabx.json"
MAX_BYTES = 1024 * 1024
SHA = re.compile(r"[0-9a-fA-F]{40}\Z")
EVIDENCE_REF = re.compile(r"EV-[A-Za-z0-9][A-Za-z0-9_-]{3,63}\Z")
STATES = {"pending", "passed", "failed", "blocked"}


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON possui chave duplicada")
        result[key] = value
    return result


def _bad_constant(_):
    raise ValueError("JSON possui numero nao finito")


def read_json(path):
    file = Path(path)
    if file.is_symlink() or not file.is_file() or file.stat().st_size > MAX_BYTES:
        raise ValueError("arquivo ausente, simbolico ou grande demais")
    return json.loads(file.read_text(encoding="utf-8"),
                      object_pairs_hook=_unique_keys, parse_constant=_bad_constant)


def normalize_sha(value):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise ValueError("SHA Git completo obrigatorio")
    return value.lower()


def registry_ids(root=ROOT):
    """Confere integridade dos modelos originais, sem alterá-los."""
    root = Path(root)
    deferred = read_json(root / OPS_FILE)
    if (not isinstance(deferred, dict)
            or deferred.get("schema_version") != 1
            or deferred.get("project") != "AXE PABX"
            or deferred.get("operational_go_authorized") is not False):
        raise ValueError("cadastro de provas operacionais inconsistente")
    records = deferred.get("pending_checks")
    if not isinstance(records, list) or len(records) != 15:
        raise ValueError("esperadas exatamente 15 provas operacionais")
    ids = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("prova operacional malformada")
        ident = record.get("id")
        if (not isinstance(ident, str)
                or not re.fullmatch(r"PABX-OPS-(?:0[8-9]|1[0-6])-[A-Z0-9-]{2,40}", ident)
                or record.get("status") != "DEFERRED_NOT_EXECUTED"
                or record.get("homologation_required") is not True
                or any(record.get(k) is not None
                       for k in ("evidence", "executed_at", "approved_at"))):
            raise ValueError("prova operacional nao esta diferida corretamente")
        ids.append(ident)
    if len(set(ids)) != 15:
        raise ValueError("IDs de prova duplicados")

    model = read_json(root / HOMOLOG_FILE)
    if (not isinstance(model, dict)
            or model.get("schema_version") != 1
            or model.get("source_commit") is not None
            or not isinstance(model.get("checks"), dict)
            or set(model["checks"]) != {key for key, _ in SCENARIOS}):
        raise ValueError("modelo de homologacao inconsistente")
    if any(not isinstance(row, dict) or row.get("status") != "pending"
           or row.get("evidence") != "" for row in model["checks"].values()):
        raise ValueError("modelo-base nao pode alegar homologacao")
    return ids


def make_packet(source_commit, root=ROOT):
    sha = normalize_sha(source_commit)
    ids = registry_ids(root)
    return {
        "schema_version": 1,
        "source_commit": sha,
        "homologation": {
            "schema_version": 1,
            "source_commit": sha,
            "checks": {
                key: {"status": "pending", "evidence": ""}
                for key, _ in SCENARIOS
            },
        },
        "operational_checks": {
            ident: {"status": "pending", "evidence": ""} for ident in ids
        },
        "operational_go_authorized": False,
    }


def evaluate(packet, expected_sha, root=ROOT):
    """Apenas cobertura DECLARADA; autenticidade e GO exigem revisão externa."""
    sha = normalize_sha(expected_sha)
    if not isinstance(packet, dict) or set(packet) != {
        "schema_version", "source_commit", "homologation",
        "operational_checks", "operational_go_authorized"
    }:
        raise ValueError("estrutura do pacote invalida")
    if (type(packet["schema_version"]) is not int or packet["schema_version"] != 1
            or packet["operational_go_authorized"] is not False
            or normalize_sha(packet["source_commit"]) != sha):
        raise ValueError("versao, SHA ou politica NO-GO inconsistente")

    homologation = packet["homologation"]
    if not isinstance(homologation, dict) or not isinstance(homologation.get("checks"), dict):
        raise ValueError("homologacao malformada")
    for record in homologation["checks"].values():
        if not isinstance(record, dict) or set(record) != {"status", "evidence"}:
            raise ValueError("cenario de homologacao malformado")
        state, ref = record["status"], record["evidence"]
        if not isinstance(state, str) or state not in STATES:
            raise ValueError("estado de homologacao invalido")
        if not isinstance(ref, str) or (ref and not EVIDENCE_REF.fullmatch(ref)):
            raise ValueError("referencia de homologacao invalida")
        if (state == "passed" and not ref) or (state == "pending" and ref):
            raise ValueError("referencia incoerente com status da homologacao")
    result = summarize_homologation(homologation)
    if result["source_commit"] != sha:
        raise ValueError("homologacao nao corresponde ao SHA do pacote")

    ids = registry_ids(root)
    checks = packet["operational_checks"]
    if not isinstance(checks, dict) or set(checks) != set(ids):
        raise ValueError("provas operacionais ausentes ou extras")

    counts = {state: 0 for state in sorted(STATES)}
    for ident in ids:
        entry = checks[ident]
        if not isinstance(entry, dict) or set(entry) != {"status", "evidence"}:
            raise ValueError("registro operacional malformado")
        state = entry["status"]
        ref = entry["evidence"]
        if not isinstance(state, str) or state not in STATES:
            raise ValueError("estado operacional desconhecido")
        if not isinstance(ref, str) or (ref and not EVIDENCE_REF.fullmatch(ref)):
            raise ValueError("referencia de evidencia invalida")
        if (state == "passed" and not ref) or (state == "pending" and ref):
            raise ValueError("evidencia incoerente com estado operacional")
        counts[state] += 1

    ready = result["gate_ready"] and counts["passed"] == len(ids)
    return {
        "schema_version": 1,
        "source_commit": sha,
        "engineering_rc_verified_by_tool": False,
        "homologation_declared_passed": result["counts"]["passed"],
        "homologation_total": result["total"],
        "homologation_declared_percent": result["coverage_percent"],
        "operational_declared_passed": counts["passed"],
        "operational_total": len(ids),
        "operational_declared_percent": round(counts["passed"] * 100 / len(ids), 1),
        "operational_counts": counts,
        "ready_for_independent_review": ready,
        "decision": ("EVIDENCE_REVIEW_REQUIRED_NO_GO" if ready
                     else "PENDING_EVIDENCE_NO_GO"),
        "evidence_authenticity_verified_by_tool": False,
        "source_sha_verified_against_runtime": False,
        "real_tests_executed_by_tool": False,
        "operational_go_authorized": False,
        "production_deployment_performed": False,
    }


def write_new_file(path, payload):
    """Cria o modelo com permissao 0600, sem sobrescrever nem seguir symlink."""
    data = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--init", type=Path, help="novo JSON local fora do repositorio")
    mode.add_argument("--evaluate", type=Path, help="JSON preenchido, somente leitura")
    parser.add_argument("--sha", required=True, help="SHA completo do codigo a homologar")
    args = parser.parse_args(argv)
    try:
        if args.init is not None:
            payload = make_packet(args.sha)
            write_new_file(args.init, payload)
            report = evaluate(payload, args.sha)
            report["local_template_created"] = True
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        report = evaluate(read_json(args.evaluate), args.sha)
    except (OSError, ValueError, TypeError, UnicodeError, json.JSONDecodeError):
        print("Pacote rejeitado: dados invalidos ou arquivo inacessivel; "
              "nenhuma homologacao ou GO concedido", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ready_for_independent_review"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
