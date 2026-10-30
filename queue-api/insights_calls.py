"""Cinco relatórios locais de chamadas com seleção exata por empresa.

Consome os registros JSONL já produzidos pelo CallLogStore. Nenhum
número do chamador, mídia ou conteúdo de chamada é exibido.
"""
from collections import Counter
from statistics import median

from insights_common import percent, tenant_rows, valid_day, valid_seconds


def _calls(records, tenant):
    selected = tenant_rows(records, tenant)
    return [
        row for row in selected
        if isinstance(row.get("disposition"), str)
        and 0 < len(row["disposition"]) <= 32
    ]


def call_volume_by_day(records, tenant):
    """01. Série diária de chamadas classificadas para o tenant."""
    counts = Counter()
    for row in _calls(records, tenant):
        day = valid_day(row.get("date"))
        if day is not None:
            counts[day] += 1
    return dict(sorted(counts.items()))


def call_answer_rate(records, tenant):
    """02. Taxa de chamadas atendidas no total observado."""
    rows = _calls(records, tenant)
    answered = sum(row["disposition"] == "ANSWERED" for row in rows)
    return {"answered": answered, "total": len(rows),
            "answer_rate_percent": percent(answered, len(rows))}


def call_missed_rate(records, tenant):
    """03. Taxa de não atendidas; não equivale a abandono de fila."""
    rows = _calls(records, tenant)
    missed = sum(row["disposition"] != "ANSWERED" for row in rows)
    return {"not_answered": missed, "total": len(rows),
            "not_answered_rate_percent": percent(missed, len(rows))}


def call_talk_time(records, tenant):
    """04. Total, média e mediana de duração válida das atendidas."""
    rows = _calls(records, tenant)
    durations = [
        duration for row in rows if row["disposition"] == "ANSWERED"
        for duration in [valid_seconds(row.get("billable_seconds"))]
        if duration is not None
    ]
    return {
        "answered_with_valid_duration": len(durations),
        "total_seconds": round(sum(durations), 1),
        "average_seconds": round(sum(durations) / len(durations), 1) if durations else None,
        "median_seconds": round(median(durations), 1) if durations else None,
    }


def call_peak_day(records, tenant):
    """05. Dia de maior volume; empate resolvido pelo dia mais antigo."""
    series = call_volume_by_day(records, tenant)
    if not series:
        return {"date": None, "calls": 0}
    day, volume = min(series.items(), key=lambda pair: (-pair[1], pair[0]))
    return {"date": day, "calls": volume}
