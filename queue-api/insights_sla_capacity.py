"""Cinco métricas operacionais adicionais de SLA histórico (76-80).

Fonte: JSONL de histórico SLA de filas. Sem alterar políticas Asterisk.
A meta de 80% é apenas exemplo, não regra contratual.
"""
from collections import defaultdict
from datetime import date

from insights_common import percent
from insights_sla_history import _history


def sla_out_of_target_by_queue(records, tenant):
    """76. Chamadas oferecidas fora do limiar de SLA por fila."""
    counters = defaultdict(lambda: [0, 0])
    for row in _history(records, tenant):
        counters[row["queue"]][0] += row["offered"]
        counters[row["queue"]][1] += row["within"]
    return {
        queue: {"offered": total, "within_sla": within,
                "outside_sla": total - within}
        for queue, (total, within) in sorted(counters.items())
    }


def sla_monthly_weighted_rate(records, tenant):
    """77. SLA mensal ponderado por chamadas oferecidas."""
    counters = defaultdict(lambda: [0, 0])
    for row in _history(records, tenant):
        key = row["date"][:7]
        counters[key][0] += row["offered"]
        counters[key][1] += row["within"]
    return {
        month: {"offered": total, "within_sla": within,
                "sla_percent": percent(within, total)}
        for month, (total, within) in sorted(counters.items())
    }


def sla_most_loaded_queue(records, tenant):
    """78. Fila de maior volume; empate pela identificação ordenada."""
    totals = defaultdict(int)
    for row in _history(records, tenant):
        totals[row["queue"]] += row["offered"]
    if not totals:
        return {"queue": None, "offered": 0}
    queue = min(totals, key=lambda name: (-totals[name], name))
    return {"queue": queue, "offered": totals[queue]}


def sla_weekday_weighted_rate(records, tenant):
    """79. SLA ponderado por dia da semana (segunda-feira=0)."""
    counters = defaultdict(lambda: [0, 0])
    for row in _history(records, tenant):
        weekday = str(date.fromisoformat(row["date"]).weekday())
        counters[weekday][0] += row["offered"]
        counters[weekday][1] += row["within"]
    return {
        str(day): {"offered": counters[str(day)][0],
                   "within_sla": counters[str(day)][1],
                   "sla_percent": percent(counters[str(day)][1],
                                          counters[str(day)][0])}
        for day in range(7)
    }


def sla_latest_recorded_day(records, tenant):
    """80. Data mais recente com métricas válidas, sem inventar atualidade."""
    rows = _history(records, tenant)
    if not rows:
        return {"date": None, "offered_on_day": 0, "within_sla_on_day": 0}
    latest = max(row["date"] for row in rows)
    on_day = [r for r in rows if r["date"] == latest]
    return {"date": latest,
            "offered_on_day": sum(r["offered"] for r in on_day),
            "within_sla_on_day": sum(r["within"] for r in on_day)}
