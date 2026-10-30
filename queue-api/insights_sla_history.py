"""Cinco métricas de histórico SLA de filas por tenant (fila-tN[-sufixo])."""
from collections import defaultdict

from insights_common import percent, require_tenant, valid_day
import re

QUEUE_RE = re.compile(r"fila-(t[1-9][0-9]*)(?:-[a-z0-9_-]{1,40})?\Z")


def _history(records, tenant):
    require_tenant(tenant)
    if not isinstance(records, list) or len(records) > 20000:
        raise ValueError("historico SLA invalido")
    out = []
    for row in records:
        if not isinstance(row, dict):
            continue
        queue = row.get("queue")
        match = QUEUE_RE.fullmatch(queue) if isinstance(queue, str) else None
        if not match or match.group(1) != tenant:
            continue
        day = valid_day(row.get("date"))
        offered, within = row.get("offered"), row.get("within_sla")
        if (day is None or type(offered) is not int or type(within) is not int
                or not 1 <= offered <= 10_000_000 or not 0 <= within <= offered):
            continue
        # Desconsiderar percentual armazenado: recalcular sempre dos contadores.
        out.append({"queue": queue, "date": day, "offered": offered, "within": within})
    return out


def sla_weighted_rate(records, tenant):
    """51. SLA geral ponderado pelo volume, não média simples de filas."""
    rows = _history(records, tenant)
    offered = sum(r["offered"] for r in rows)
    within = sum(r["within"] for r in rows)
    return {"offered": offered, "within_sla": within,
            "weighted_sla_percent": percent(within, offered)}


def sla_offered_by_day(records, tenant):
    """52. Volume de chamadas oferecidas por dia."""
    totals = defaultdict(int)
    for row in _history(records, tenant):
        totals[row["date"]] += row["offered"]
    return dict(sorted(totals.items()))


def sla_rate_by_queue(records, tenant):
    """53. SLA agregado por fila identificada de forma exata."""
    totals = defaultdict(lambda: [0, 0])
    for row in _history(records, tenant):
        totals[row["queue"]][0] += row["within"]
        totals[row["queue"]][1] += row["offered"]
    return {q: {"within_sla": x[0], "offered": x[1],
                "sla_percent": percent(x[0], x[1])}
            for q, x in sorted(totals.items())}


def sla_days_below_eighty(records, tenant):
    """54. Quantos dias ficaram abaixo da meta ilustrativa de 80%."""
    totals = defaultdict(lambda: [0, 0])
    for row in _history(records, tenant):
        totals[row["date"]][0] += row["within"]
        totals[row["date"]][1] += row["offered"]
    return {"days_measured": len(totals),
            "days_below_80_percent": sum(percent(w, o) < 80 for w, o in totals.values())}


def sla_worst_day(records, tenant):
    """55. Dia de menor SLA ponderado, sem dados pessoais."""
    totals = defaultdict(lambda: [0, 0])
    for row in _history(records, tenant):
        totals[row["date"]][0] += row["within"]
        totals[row["date"]][1] += row["offered"]
    if not totals:
        return {"date": None, "sla_percent": None, "offered": 0}
    day = min(totals, key=lambda d: (totals[d][0] / totals[d][1], d))
    within, offered = totals[day]
    return {"date": day, "sla_percent": percent(within, offered), "offered": offered}
