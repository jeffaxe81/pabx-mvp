"""Cinco métricas locais de idade das pendências de callback (71-75).

Leitura de snapshot JSON, sem discagem/AMI e sem expor PII.
Amostras com data no futuro não entram em métricas de idade.
"""
from collections import Counter
from datetime import datetime, timezone
from statistics import median
import time

from insights_callbacks import _callbacks
from insights_common import percent


def _pending_ages(records, tenant):
    now = time.time()
    return [
        now - row["at"] for row in _callbacks(records, tenant)
        if row["status"] == "pendente" and row["at"] <= now
    ]


def callback_oldest_pending_seconds(records, tenant):
    """71. Idade da pendência mais antiga em segundos."""
    ages = _pending_ages(records, tenant)
    return {"pending_with_valid_date": len(ages),
            "oldest_seconds": round(max(ages), 1) if ages else None}


def callback_median_pending_seconds(records, tenant):
    """72. Mediana da idade das pendências, sem IDs de contatos."""
    ages = _pending_ages(records, tenant)
    return {"pending_with_valid_date": len(ages),
            "median_seconds": round(median(ages), 1) if ages else None}


def callback_pending_age_bands(records, tenant):
    """73. Distribuição de espera em 0-5m, 5-30m, 30m-2h, 2h+."""
    bands = {"under_5m": 0, "5m_to_30m": 0, "30m_to_2h": 0, "over_2h": 0}
    for age in _pending_ages(records, tenant):
        if age < 300:
            bands["under_5m"] += 1
        elif age < 1800:
            bands["5m_to_30m"] += 1
        elif age < 7200:
            bands["30m_to_2h"] += 1
        else:
            bands["over_2h"] += 1
    return bands


def callback_pending_over_one_hour(records, tenant):
    """74. Pendências com idade igual ou superior a uma hora."""
    ages = _pending_ages(records, tenant)
    delayed = sum(age >= 3600 for age in ages)
    return {"pending_with_valid_date": len(ages), "at_least_one_hour": delayed,
            "at_least_one_hour_percent": percent(delayed, len(ages))}


def callback_pending_created_weekday(records, tenant):
    """75. Pendências por dia da semana UTC em que foram solicitadas."""
    counts = Counter()
    now = time.time()
    for row in _callbacks(records, tenant):
        if row["status"] != "pendente" or row["at"] > now:
            continue
        weekday = datetime.fromtimestamp(row["at"], tz=timezone.utc).weekday()
        counts[str(weekday)] += 1
    return {str(day): counts[str(day)] for day in range(7)}
