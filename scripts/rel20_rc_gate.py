#!/usr/bin/env python3
"""REL-20: valida somente a versao candidata LOCAL; nunca autoriza producao.

O gate e estrutural: provas reais e autenticidade de CI sao verificadas fora
deste script. Uma tag Git nao e criada por esta ferramenta.
"""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "docs/releases/axe-pabx-0.1.0-rc.1.json"
RELEASE = "docs/release-fechamento-20-entregas.md"
OPERATIONS = "docs/quality/provas-operacionais-diferidas.json"
HOMOLOGATION = "docs/modelo-homologacao-pabx.json"
VERSION = "VERSION"
VERSION_RE = re.compile(r"0\.[0-9]+\.[0-9]+-rc\.[1-9][0-9]*\Z")
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")


def _duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("REL20-JSON-DUPLICATE")
        result[key] = value
    return result


def _read(root, path, *, limit=512 * 1024):
    target = root / path
    if target.is_symlink() or not target.is_file():
        raise ValueError("REL20-FILE-INVALID:" + path)
    if target.stat().st_size > limit:
        raise ValueError("REL20-FILE-TOO-LARGE:" + path)
    return target.read_text(encoding="utf-8")


def _json(root, path):
    try:
        return json.loads(_read(root, path), object_pairs_hook=_duplicates,
                          parse_constant=lambda v: (_ for _ in ()).throw(ValueError("REL20-JSON-CONSTANT")))
    except json.JSONDecodeError as e:
        raise ValueError("REL20-JSON-INVALID:" + path) from e


def verify(root=ROOT):
    root = Path(root)
    version = _read(root, VERSION, limit=128).strip()
    if not VERSION_RE.fullmatch(version):
        raise ValueError("REL20-VERSION-INVALID")
    manifest = _json(root, MANIFEST)
    if not isinstance(manifest, dict):
        raise ValueError("REL20-MANIFEST-INVALID")
    expected = {
        "schema_version": 1, "name": "AXE PABX",
        "version": version, "channel": "local-release-candidate",
        "scope": "PABX_PURO",
        "milestones_total": 20, "milestones_completed": 20,
        "candidate_prepared": True,
        "artifact_kind": "repository-snapshot-at-merge-commit",
        "git_tag_created_by_this_change": False,
        "contact_center_in_scope": False, "ai_in_scope": False,
        "real_telecom_operator_tested": False, "physical_ip_phone_tested": False,
        "production_deployment_executed": False,
        "operational_go_authorized": False,
        "operational_homologation_completed": False,
        "external_evidence_required": True, "review_required_before_production": True,
        "release_acceptance": "ENGINEERING_RC_ONLY_NO_GO",
    }
    if any(type(manifest.get(k)) is not type(v) or manifest[k] != v
           for k, v in expected.items()):
        raise ValueError("REL20-MANIFEST-CONFLICT")
    if not isinstance(manifest.get("baseline_commit"), str) or not SHA_RE.fullmatch(manifest["baseline_commit"]):
        raise ValueError("REL20-BASELINE-INVALID")
    if not isinstance(manifest.get("created_on"), str) or manifest["created_on"] != "2026-11-01":
        raise ValueError("REL20-DATE-INVALID")

    checklist = _read(root, RELEASE)
    rows = re.findall(r"(?m)^- \[([ x])\] \*\*REL-([0-9]{2}) — ([^\n]+)", checklist)
    if len(rows) != 20 or [int(n) for _, n, _ in rows] != list(range(1, 21)):
        raise ValueError("REL20-MILESTONES-INVALID")
    if any(mark != "x" for mark, _, _ in rows):
        raise ValueError("REL20-MILESTONES-INCOMPLETE")
    if ("20/20 concluídas (100%)" not in checklist
            or "100% (20/20)" not in checklist
            or "REL-20 — Release candidate local" not in checklist):
        raise ValueError("REL20-CHECKLIST-INCONSISTENT")
    if ("produção permanece NO-GO" not in checklist
            or "operacional" not in checklist):
        raise ValueError("REL20-NOGO-MISSING")
    if version not in rows[-1][2]:
        raise ValueError("REL20-VERSION-NOT-LINKED")

    deferred = _json(root, OPERATIONS)
    items = deferred.get("pending_checks") if isinstance(deferred, dict) else None
    if (not isinstance(items, list) or len(items) != 15
            or deferred.get("operational_go_authorized") is not False
            or any(not isinstance(x, dict) or x.get("status") != "DEFERRED_NOT_EXECUTED"
                   or x.get("evidence") is not None for x in items)):
        raise ValueError("REL20-OPS-GATE-INVALID")
    homologation = _json(root, HOMOLOGATION)
    checks = homologation.get("checks") if isinstance(homologation, dict) else None
    if (not isinstance(checks, dict) or len(checks) != 13
            or homologation.get("source_commit") is not None
            or any(x.get("status") != "pending" or x.get("evidence") != ""
                   for x in checks.values() if isinstance(x, dict))
            or any(not isinstance(x, dict) for x in checks.values())):
        raise ValueError("REL20-HOMOLOGATION-INVALID")
    return {
        "schema_version": 1,
        "version": version,
        "kind": "engineering_release_candidate_local",
        "release_checklist_completed": 20,
        "release_checklist_total": 20,
        "engineering_release_percent": 100,
        "deferred_operational_checks": 15,
        "unperformed_manual_homologation_scenarios": 13,
        "git_tag_created_by_this_tool": False,
        "ci_approval_verified_by_this_tool": False,
        "production_deployment_performed": False,
        "operational_go_authorized": False,
        "decision": "RC_LOCAL_READY_FOR_TECHNICAL_REVIEW_NO_GO",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        result = verify(args.root)
    except (ValueError, OSError, UnicodeError, TypeError) as exc:
        parser.exit(2, "REL20: gate bloqueado: " + str(exc) + "\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
