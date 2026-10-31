"""Indicadores locais 106–110 para acompanhamento histórico de SLA.

Usa contadores da fila por tenant; limiar de 80% é ilustrativo e não
constitui SLA contratual. A ausência de registros não implica SLA zero.
"""
from collections import defaultdict
from datetime import date, timedelta

from insights_common import percent
from insights_sla_history import _history


def _daily(records, tenant):
    out = defaultdict(lambda: [0, 0])
    for row in _history(records, tenant):
        out[row["date"]][0] += row["within"]
        out[row["date"]][1] += row["offered"]
    return out


def sla_consecutive_days_below_eighty(records, tenant):
    """106. Maior sequência consecutiva de datas abaixo de 80%."""
    totals = _daily(records, tenant)
    longest, current, previous = 0, 0, None
    for day in sorted(totals):
        within, offered = totals[day]
        if within * 5 < offered * 4:
            current = current + 1 if (previous is not None and
                         date.fromisoformat(day) - previous == timedelta(days=1)) else 1
            longest = max(longest, current)
            previous = date.fromisoformat(day)
        else:
            current, previous = 0, None
    return {"days_measured": len(totals), "longest_streak_below_80": longest}


def sla_monthly_outside_target_count(records, tenant):
    """107. Contador de chamadas fora do SLA por mês."""
    totals = defaultdict(lambda: [0, 0])
    for row in _history(records, tenant):
        item = totals[row["date"][:7]]
        item[0] += row["offered"]
        item[1] += row["within"]
    return {month: {"offered": offered, "outside_sla": offered - within}
            for month, (offered, within) in sorted(totals.items())}


def sla_queue_traffic_share(records, tenant):
    """108. Participação percentual de volume por fila no período."""
    volumes = defaultdict(int)
    for row in _history(records, tenant):
        volumes[row["queue"]] += row["offered"]
    overall = sum(volumes.values())
    return {queue: {"offered": offered, "traffic_percent": percent(offered, overall)}
            for queue, offered in sorted(volumes.items())}


def sla_lowest_rate_queue_min_ten(records, tenant):
    """109. Menor taxa por fila, exigindo ao menos dez ofertas."""
    totals = defaultdict(lambda: [0, 0])
    for row in _history(records, tenant):
        item = totals[row["queue"]]
        item[0] += row["within"]
        item[1] += row["offered"]
    eligible = {q: v for q, v in totals.items() if v[1] >= 10}
    if not eligible:
        return {"queue": None, "within_sla": 0, "offered": 0,
                "sla_percent": None, "minimum_offered": 10}
    queue = min(eligible, key=lambda q: (eligible[q][0] / eligible[q][1], q))
    within, offered = eligible[queue]
    return {"queue": queue, "within_sla": within, "offered": offered,
            "sla_percent": percent(within, offered), "minimum_offered": 10}


def sla_best_day(records, tenant):
    """110. Dia de maior SLA ponderado e volume registrado."""
    totals = _daily(records, tenant)
    if not totals:
        return {"date": None, "sla_percent": None, "offered": 0}
    # Em percentuais iguais, priorizar a amostra de maior volume.
    # Persistindo empate, escolher a data mais antiga.
    day = min(totals, key=lambda d: (-totals[d][0] / totals[d][1], -totals[d][1], d))
    within, offered = totals[day]
    return {"date": day, "sla_percent": percent(within, offered), "offered": offered}
