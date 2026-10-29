#!/usr/bin/env python3
"""Medição adicional de avanço técnico; nunca substitui aceite/GO formal."""
import argparse
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs" / "plano-16-semanas-pabx.json"
CRITERIA = ROOT / "docs" / "quality" / "progresso-tecnico-criterios.json"
MAX_BYTES = 1024 * 1024


def _unique_keys(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("JSON ambiguo: chave duplicada")
        out[key] = value
    return out


def _read(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("arquivo de progresso invalido")
    return json.loads(path.read_text(encoding="utf-8"),
                      object_pairs_hook=_unique_keys,
                      parse_constant=lambda _: (_ for _ in ()).throw(
                          ValueError("numero JSON nao finito")))


def _percent(units, total):
    return float((Decimal(units) * 100 / Decimal(total)).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP))


def calculate(plan, evidence, *, root=ROOT):
    """Conta marcos prontos + fração explícita dos marcos em andamento.

    A medição fracionária é somente engenharia/laboratório. Não muda
    'status', não declara autorização de produção nem aceita CI inventada.
    """
    if not isinstance(plan, dict) or not isinstance(evidence, dict):
        raise ValueError("estrutura ausente")
    milestones = plan.get("milestones")
    partials = evidence.get("partial_milestones")
    if (plan.get("schema_version") != 1 or evidence.get("schema_version") != 1
            or not isinstance(milestones, list) or len(milestones) != 16
            or not isinstance(partials, list)):
        raise ValueError("plano ou evidencia invalidos")
    weeks = {entry.get("week"): entry for entry in milestones if isinstance(entry, dict)}
    if set(weeks) != set(range(1, 17)):
        raise ValueError("marcos ausentes ou repetidos")
    if any(m.get("status") not in ("done", "in_progress", "planned")
           for m in milestones):
        raise ValueError("status de marco invalido")
    formal = sum(m["status"] == "done" for m in milestones)
    technical = Decimal(formal)
    summaries = []
    seen_weeks = set()
    root = Path(root)
    for item in partials:
        if not isinstance(item, dict) or type(item.get("week")) is not int:
            raise ValueError("marco parcial invalido")
        week = item["week"]
        if (week in seen_weeks or week not in weeks
                or weeks[week]["status"] != "in_progress"):
            raise ValueError("marco parcial duplicado ou nao esta em andamento")
        seen_weeks.add(week)
        criteria = item.get("criteria")
        if not isinstance(criteria, list) or not criteria:
            raise ValueError("criterios ausentes")
        ids = set()
        verified = 0
        for check in criteria:
            if not isinstance(check, dict) or not isinstance(check.get("id"), str):
                raise ValueError("criterio malformado")
            if not check["id"] or check["id"] in ids:
                raise ValueError("criterio repetido")
            ids.add(check["id"])
            if check.get("state") not in ("verified_lab", "pending"):
                raise ValueError("estado de criterio invalido")
            path = check.get("evidence_file")
            if not isinstance(path, str):
                raise ValueError("referencia ausente")
            rel = PurePosixPath(path)
            if (rel.is_absolute() or ".." in rel.parts or not rel.parts
                    or not (root / path).is_file()
                    or (root / path).is_symlink()):
                raise ValueError("arquivo de evidencia nao existe ou e inseguro")
            if check["state"] == "verified_lab":
                if (not isinstance(check.get("ci_job"), str)
                        or not check["ci_job"].strip()):
                    raise ValueError("prova automatizada nao vinculada")
                verified += 1
            elif check.get("ci_job") is not None:
                raise ValueError("criterio pendente marcado como verificado")
        technical += Decimal(verified) / Decimal(len(criteria))
        summaries.append({"week": week, "verified": verified,
                          "total": len(criteria),
                          "percent": _percent(verified, len(criteria))})
    return {
        "formal_completed": formal,
        "formal_total": len(milestones),
        "formal_percent": _percent(formal, len(milestones)),
        "technical_equivalent_units": float(technical),
        "technical_percent": _percent(technical, len(milestones)),
        "partial_milestones": summaries,
        "operational_go_authorized": plan.get("operational_go_authorized") is True,
        "technical_metric_is_operational_homologation": False,
        "note": "Medida fracionaria de engenharia/laboratorio; os marcos seguem in_progress ate aceite integral."
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--criteria", type=Path, default=CRITERIA)
    args = parser.parse_args(argv)
    try:
        report = calculate(_read(args.plan), _read(args.criteria))
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as error:
        parser.exit(2, "Progresso nao validado: " + type(error).__name__ + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
