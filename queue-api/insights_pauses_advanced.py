"""Cinco métricas adicionais de pausas encerradas dos atendentes."""
from collections import defaultdict
from datetime import date
from statistics import median
from insights_pauses import _pauses


def pause_average_duration(records, tenant):
    """41. Média por pausa encerrada com duração conhecida."""
    values = [r["seconds"] for r in _pauses(records, tenant)]
    return round(sum(values) / len(values), 1) if values else None


def pause_median_duration(records, tenant):
    """42. Mediana por pausa encerrada."""
    values = [r["seconds"] for r in _pauses(records, tenant)]
    return round(median(values), 1) if values else None


def pause_duration_bands(records, tenant):
    """43. Distribuição de pausas curtas, médias e longas."""
    bands = {"up_to_300": 0, "301_to_1800": 0, "over_1800": 0}
    for r in _pauses(records, tenant):
        sec = r["seconds"]
        bucket = "up_to_300" if sec <= 300 else (
            "301_to_1800" if sec <= 1800 else "over_1800"
        )
        bands[bucket] += 1
    return bands


def pause_weekday_seconds(records, tenant):
    """44. Total de pausas por dia da semana, apenas data válida."""
    totals = {str(i): 0.0 for i in range(7)}
    for r in _pauses(records, tenant):
        if r["day"]:
            weekday = str(date.fromisoformat(r["day"]).weekday())
            totals[weekday] += r["seconds"]
    return {weekday: round(value, 1) for weekday, value in totals.items()}


def pause_active_agent_count(records, tenant):
    """45. Quantos ramais tiveram alguma pausa encerrada no arquivo."""
    agents = {r["extension"] for r in _pauses(records, tenant)}
    return {"agents_with_closed_pauses": len(agents)}
