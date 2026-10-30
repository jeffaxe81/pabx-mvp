"""Cinco indicadores locais de presença manual por tenant (81-85).

A fonte é o mapa JSON privado `presence.json`, transformado em registros
pelo leitor local. As notas livres nunca são retornadas.
Os números não representam o BLF automático nem disponibilidade SIP.
"""
from collections import Counter
from datetime import datetime, timezone
import math
import time

from insights_common import AGENT_RE, percent, tenant_rows

ALLOWED = ("disponivel", "ausente", "reuniao", "ferias")
MAX_TIMESTAMP = 4102444800


def _presence(records, tenant):
    chosen = []
    for row in tenant_rows(records, tenant, from_agent=True):
        status = row.get("status")
        if type(status) is not str or status not in ALLOWED:
            continue
        timestamp = row.get("updated_at")
        if (type(timestamp) not in (int, float)
                or not math.isfinite(timestamp) or timestamp < 0
                or timestamp > MAX_TIMESTAMP):
            timestamp = None
        chosen.append({"status": status, "at": timestamp})
    return chosen


def presence_total_overrides(records, tenant):
    """81. Quantidade de overrides manuais válidos por empresa."""
    return {"manual_overrides": len(_presence(records, tenant))}


def presence_by_status(records, tenant):
    """82. Distribuição dos estados manuais; não indica estado BLF."""
    counts = Counter(row["status"] for row in _presence(records, tenant))
    return {status: counts[status] for status in ALLOWED}


def presence_updated_by_day(records, tenant):
    """83. Quantidade de atualizações mais recentes por dia UTC."""
    counts = Counter()
    for row in _presence(records, tenant):
        if row["at"] is not None:
            day = datetime.fromtimestamp(row["at"], tz=timezone.utc).date().isoformat()
            counts[day] += 1
    return dict(sorted(counts.items()))


def presence_older_than_week(records, tenant):
    """84. Overrides com última alteração datada há pelo menos 7 dias."""
    now = time.time()
    measured = [r for r in _presence(records, tenant)
                if r["at"] is not None and r["at"] <= now]
    old = sum(now - r["at"] >= 7 * 86400 for r in measured)
    return {"measured_overrides": len(measured), "seven_days_or_older": old,
            "seven_days_or_older_percent": percent(old, len(measured))}


def presence_missing_valid_timestamp(records, tenant):
    """85. Overrides com ausência de data válida; não inventar idade."""
    rows = _presence(records, tenant)
    missing = sum(r["at"] is None for r in rows)
    return {"manual_overrides": len(rows), "without_valid_updated_at": missing}
