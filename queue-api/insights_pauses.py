"""Cinco visões de histórico de pausa já encerrada, por empresa."""
from collections import defaultdict
from datetime import datetime
from math import isfinite

from insights_common import tenant_rows, valid_seconds


def _pauses(records, tenant):
    valid = []
    allowed_reasons = {"almoço", "almoco", "banheiro", "descanso", "reunião",
                       "reuniao", "treinamento", "pausa técnica", "pausa tecnica"}
    for row in tenant_rows(records, tenant, from_agent=True):
        seconds = valid_seconds(row.get("duration_seconds"))
        if seconds is None:
            continue
        reason = row.get("reason")
        if not isinstance(reason, str) or not 0 < len(reason) <= 120 or not reason.isprintable():
            reason = "sem motivo"
        elif reason.strip().lower() not in allowed_reasons:
            # Motivo livre pode conter dados pessoais: não reproduzir texto arbitrário.
            reason = "outros"
        timestamp = row.get("started_at")
        day = None
        if (type(timestamp) in (int, float) and isfinite(timestamp)
                and 0 <= timestamp <= 4102444800):
            try:
                day = datetime.fromtimestamp(timestamp).date().isoformat()
            except (ValueError, OverflowError, OSError):
                pass
        valid.append({
            "extension": row["extension"], "reason": reason,
            "seconds": seconds, "day": day,
        })
    return valid


def pause_total_time(records, tenant):
    """11. Quantidade de pausas e duração total conhecida."""
    rows = _pauses(records, tenant)
    return {"pauses": len(rows), "total_seconds": round(sum(r["seconds"] for r in rows), 1)}


def pause_by_reason(records, tenant):
    """12. Total de segundos e ocorrências por motivo."""
    groups = defaultdict(list)
    for row in _pauses(records, tenant):
        groups[row["reason"]].append(row["seconds"])
    return {
        reason: {"count": len(values), "seconds": round(sum(values), 1)}
        for reason, values in sorted(groups.items())
    }


def pause_by_agent(records, tenant):
    """13. Distribuição de pausas por ramal do tenant selecionado."""
    groups = defaultdict(list)
    for row in _pauses(records, tenant):
        groups[row["extension"]].append(row["seconds"])
    return {
        agent: {"count": len(values), "seconds": round(sum(values), 1)}
        for agent, values in sorted(groups.items())
    }


def pause_longest(records, tenant):
    """14. Maior pausa encerrada, sem inferir pausas abertas."""
    rows = _pauses(records, tenant)
    if not rows:
        return {"extension": None, "seconds": None, "reason": None}
    longest = sorted(rows, key=lambda r: (-r["seconds"], r["extension"]))[0]
    return {"extension": longest["extension"],
            "seconds": round(longest["seconds"], 1), "reason": longest["reason"]}


def pause_daily_trend(records, tenant):
    """15. Segundos de pausas encerradas por dia de início."""
    totals = defaultdict(float)
    for row in _pauses(records, tenant):
        if row["day"] is not None:
            totals[row["day"]] += row["seconds"]
    return {day: round(seconds, 1) for day, seconds in sorted(totals.items())}
