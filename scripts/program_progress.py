#!/usr/bin/env python3
"""Relatório do programa AXE PABX de 16 semanas.

Valida o plano versionado, calcula o progresso declarado e mostra
bloqueios. Não consulta CI, não executa telefonia e não autoriza GO.
"""
import argparse
import json
from pathlib import Path
import re
import sys

VALID_STATUSES = {"planned", "in_progress", "blocked", "done"}
SHA = re.compile(r"[0-9a-f]{40}\Z")


def validate_plan(plan):
    if not isinstance(plan, dict) or plan.get("schema_version") != 1:
        raise ValueError("schema_version inválida")
    if plan.get("duration_weeks") != 16 or plan.get("project") != "AXE PABX":
        raise ValueError("escopo do programa inválido")
    sha = plan.get("baseline_sha")
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        raise ValueError("baseline_sha inválido")
    milestones = plan.get("milestones")
    if not isinstance(milestones, list) or len(milestones) != 16:
        raise ValueError("programa deve conter exatamente 16 marcos")
    weeks = set()
    for item in milestones:
        if not isinstance(item, dict):
            raise ValueError("marco inválido")
        week, month = item.get("week"), item.get("month")
        if type(week) is not int or not 1 <= week <= 16 or week in weeks:
            raise ValueError("semanas repetidas ou inválidas")
        weeks.add(week)
        if type(month) is not int or month != (week - 1) // 4 + 1:
            raise ValueError(f"mês incorreto na semana {week}")
        if item.get("status") not in VALID_STATUSES:
            raise ValueError("estado do marco inválido")
        for field in ("title", "acceptance", "area"):
            value = item.get(field)
            if not isinstance(value, str) or not 3 <= len(value.strip()) <= 250:
                raise ValueError(f"campo {field} inválido")
            if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
                raise ValueError(f"campo {field} contém controle")
        if type(item.get("requires_lab")) is not bool:
            raise ValueError("campo requires_lab inválido")
        pr, ci = item.get("pr_number"), item.get("ci_run_id")
        if item["status"] == "done":
            if type(pr) is not int or pr < 1 or type(ci) is not int or ci < 1:
                raise ValueError("conclusão requer PR e execução CI associadas")
        elif pr is not None or ci is not None:
            raise ValueError("marco não concluído não pode indicar CI/PR como entregue")
    if weeks != set(range(1, 17)):
        raise ValueError("numeração de semanas incompleta")
    if plan.get("operational_go_authorized") is not False:
        raise ValueError("plano não pode autorizar GO por conta própria")
    return milestones


def summarize(plan):
    milestones = validate_plan(plan)
    by_month = []
    for month in range(1, 5):
        subset = [row for row in milestones if row["month"] == month]
        done = sum(row["status"] == "done" for row in subset)
        by_month.append({
            "month": month, "done": done, "total": 4,
            "percent": round(done * 25.0, 1),
            "blocked": sum(row["status"] == "blocked" for row in subset),
        })
    done = sum(row["status"] == "done" for row in milestones)
    return {
        "project": plan["project"],
        "program": plan["program"],
        "weeks_completed": done, "weeks_total": 16,
        "program_percent": round(done * 100 / 16, 1),
        "months": by_month,
        "next_pending": [
            {"week": row["week"], "title": row["title"], "status": row["status"]}
            for row in milestones if row["status"] != "done"
        ][:5],
        "completed_prs": sorted(row["pr_number"] for row in milestones
                                if row["status"] == "done"),
        "status_source": "declarado no JSON versionado; CI e evidências não verificadas aqui",
        "real_sip_calls_executed_by_this_tool": False,
        "operational_go_authorized": False,
    }


def markdown(report):
    rows = [
        "# AXE PABX — acompanhamento de 16 semanas",
        "",
        f"Avanço do programa: **{report['program_percent']:.1f}%** "
        f"({report['weeks_completed']}/16 marcos declarados como entregues).",
        "",
        "| Mês | Marcos concluídos | Progresso | Bloqueados |",
        "|---|---:|---:|---:|",
    ]
    for m in report["months"]:
        rows.append(f"| {m['month']} | {m['done']}/4 | "
                    f"{m['percent']:.1f}% | {m['blocked']} |")
    rows.extend(["", "**Próximos marcos:**"])
    for item in report["next_pending"]:
        rows.append(f"- Semana {item['week']}: {item['title']} "
                    f"({item['status']})")
    rows.extend(["", "O relatório não executa chamadas nem comprova "
                 "CI ou autoriza implantação."])
    return "\n".join(rows) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    default = Path(__file__).resolve().parent.parent / "docs" / "plano-16-semanas-pabx.json"
    parser.add_argument("--file", default=str(default))
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    try:
        source = Path(args.file)
        if source.is_symlink() or not source.is_file():
            raise ValueError("plano ausente ou link simbólico")
        report = summarize(json.loads(source.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as err:
        print(f"Plano de 16 semanas inválido: {err}", file=sys.stderr)
        return 2
    print(markdown(report) if args.format == "markdown"
          else json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
