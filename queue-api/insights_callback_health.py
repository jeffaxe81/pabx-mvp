"""Indicadores 101–105 de saúde do catálogo de callbacks, somente leitura.

Amostras com data no futuro não são usadas para medir atraso. Não há
repetição automática, discagem ou chamada AMI.
"""
from collections import Counter
import math
import time

from insights_callbacks import _callbacks
from insights_common import percent
from callbacks import MAX_ATTEMPTS


def _valid_cutoff(as_of):
    value = time.time() if as_of is None else as_of
    if (type(value) not in (int, float) or not math.isfinite(value)
            or not 0 <= value <= 4102444800):
        raise ValueError("instante de referência inválido")
    return value


def _pending(records, tenant):
    return [r for r in _callbacks(records, tenant) if r["status"] == "pendente"]


def callback_pending_over_24h(records, tenant, as_of=None):
    """101. Pendentes com idade comprovada de pelo menos 24h."""
    now = _valid_cutoff(as_of)
    rows = [r for r in _pending(records, tenant) if r["at"] <= now]
    stale = sum(now - r["at"] >= 86400 for r in rows)
    return {"dated_pending": len(rows), "at_least_24h": stale,
            "rate_percent": percent(stale, len(rows))}


def callback_pending_over_48h(records, tenant, as_of=None):
    """102. Pendentes com idade comprovada de pelo menos 48h."""
    now = _valid_cutoff(as_of)
    rows = [r for r in _pending(records, tenant) if r["at"] <= now]
    stale = sum(now - r["at"] >= 172800 for r in rows)
    return {"dated_pending": len(rows), "at_least_48h": stale,
            "rate_percent": percent(stale, len(rows))}


def callback_pending_exhausted_attempts(records, tenant):
    """103. Pedidos pendentes cujo número de tentativas atingiu o limite."""
    rows = _pending(records, tenant)
    count = sum(r["attempts"] == MAX_ATTEMPTS for r in rows)
    return {"pending": len(rows), "attempts_exhausted": count}


def callback_completed_by_attempts(records, tenant):
    """104. Pedidos concluídos agrupados pelo número registrado de tentativas."""
    totals = Counter(r["attempts"] for r in _callbacks(records, tenant)
                     if r["status"] == "concluido")
    return {str(i): totals[i] for i in range(MAX_ATTEMPTS + 1)}


def callback_pending_share(records, tenant):
    """105. Percentual de pendentes entre pedidos de status conhecido."""
    rows = _callbacks(records, tenant)
    pending = sum(r["status"] == "pendente" for r in rows)
    return {"recognized": len(rows), "pending": pending,
            "pending_percent": percent(pending, len(rows))}
