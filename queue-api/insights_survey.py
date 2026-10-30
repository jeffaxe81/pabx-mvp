"""Cinco visões locais e agregadas de satisfação, sem identificadores de clientes."""
from collections import defaultdict

from insights_common import percent, tenant_rows, valid_day


def _surveys(records, tenant):
    return [
        row for row in tenant_rows(records, tenant)
        if type(row.get("score")) is int and 1 <= row["score"] <= 5
    ]


def survey_average_rating(records, tenant):
    """06. Nota média geral da empresa, sem inventar nota quando vazia."""
    scores = [row["score"] for row in _surveys(records, tenant)]
    return {"responses": len(scores),
            "average": round(sum(scores) / len(scores), 2) if scores else None}


def survey_rating_distribution(records, tenant):
    """07. Histograma de notas 1 a 5, com zeros explícitos."""
    counts = {str(n): 0 for n in range(1, 6)}
    for row in _surveys(records, tenant):
        counts[str(row["score"])] += 1
    return counts


def survey_positive_rate(records, tenant):
    """08. Percentual de avaliações positivas (4 e 5)."""
    rows = _surveys(records, tenant)
    positive = sum(row["score"] >= 4 for row in rows)
    return {"positive": positive, "responses": len(rows),
            "positive_rate_percent": percent(positive, len(rows))}


def survey_low_rating_rate(records, tenant):
    """09. Percentual de avaliações baixas (1 e 2)."""
    rows = _surveys(records, tenant)
    low = sum(row["score"] <= 2 for row in rows)
    return {"low": low, "responses": len(rows),
            "low_rate_percent": percent(low, len(rows))}


def survey_daily_average(records, tenant):
    """10. Tendência diária de satisfação sem expor nomes/números."""
    groups = defaultdict(list)
    for row in _surveys(records, tenant):
        day = valid_day(row.get("date"))
        if day is not None:
            groups[day].append(row["score"])
    return {
        day: {"responses": len(values), "average": round(sum(values) / len(values), 2)}
        for day, values in sorted(groups.items())
    }
