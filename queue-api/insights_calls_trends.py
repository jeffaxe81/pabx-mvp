"""Cinco séries históricas adicionais de chamadas, por empresa."""
from collections import Counter, defaultdict
from datetime import date
from insights_calls import _calls
from insights_common import percent, valid_day


def _dated(records, tenant):
    for row in _calls(records, tenant):
        day = valid_day(row.get("date"))
        if day is not None:
            yield row, date.fromisoformat(day)


def calls_weekday_volume(records, tenant):
    """26. Quantidade por dia da semana (segunda=0)."""
    counts = {str(d): 0 for d in range(7)}
    for _, day in _dated(records, tenant):
        counts[str(day.weekday())] += 1
    return counts


def calls_weekly_volume(records, tenant):
    """27. Volume por semana ISO, diferenciando ano da semana."""
    counts = Counter()
    for _, day in _dated(records, tenant):
        iso = day.isocalendar()
        counts[f"{iso.year}-W{iso.week:02d}"] += 1
    return dict(sorted(counts.items()))


def calls_monthly_volume(records, tenant):
    """28. Volume por mês fechado AAAA-MM."""
    counts = Counter(day.strftime("%Y-%m") for _, day in _dated(records, tenant))
    return dict(sorted(counts.items()))


def calls_monthly_answer_rate(records, tenant):
    """29. Atendimento mensal calculado de contadores válidos."""
    counts = defaultdict(lambda: [0, 0])
    for row, day in _dated(records, tenant):
        item = counts[day.strftime("%Y-%m")]
        item[1] += 1
        item[0] += row["disposition"] == "ANSWERED"
    return {month: {"answered": a, "total": t, "rate_percent": percent(a, t)}
            for month, (a, t) in sorted(counts.items())}


def calls_daily_answer_rate(records, tenant):
    """30. Atendimento diário calculado de contadores válidos."""
    counts = defaultdict(lambda: [0, 0])
    for row, day in _dated(records, tenant):
        item = counts[day.isoformat()]
        item[1] += 1
        item[0] += row["disposition"] == "ANSWERED"
    return {day: {"answered": a, "total": t, "rate_percent": percent(a, t)}
            for day, (a, t) in sorted(counts.items())}
