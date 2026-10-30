"""Cinco indicadores locais de callbacks por tenant (61-65), sem telefonia.

Importante: estes relatórios não autenticam o operador, não disparam
originate e não atestam homologação real do AMI.
"""
from collections import Counter
from datetime import datetime, timezone
import math

from callbacks import CALLBACK_SUMMARY_STATUSES, MAX_ATTEMPTS, _catalog_has_unique_ids
from insights_common import percent, tenant_rows


def _callbacks(records, tenant):
    # O arquivo inteiro precisa ter IDs únicos; um catálogo ambíguo não
    # pode ser usado para planejamento de callback nem para métricas.
    if not _catalog_has_unique_ids(records):
        raise ValueError("catalogo de callbacks ambiguo")
    selected = []
    for row in tenant_rows(records, tenant):
        status, attempts, requested_at = (
            row.get("status"), row.get("attempts"), row.get("requested_at")
        )
        if (status not in CALLBACK_SUMMARY_STATUSES
                or type(attempts) is not int or not 0 <= attempts <= MAX_ATTEMPTS
                or type(requested_at) not in (int, float)
                or not math.isfinite(requested_at)
                or not 0 <= requested_at <= 4102444800):
            continue
        selected.append({"status": status, "attempts": attempts, "at": requested_at})
    return selected


def callback_status_counts(records, tenant):
    """61. Distribuição por status persistido, com escopo exato."""
    counts = Counter(row["status"] for row in _callbacks(records, tenant))
    return {status: counts[status] for status in CALLBACK_SUMMARY_STATUSES}


def callback_completion_rate(records, tenant):
    """62. Êxito somente entre pedidos com resultado terminal conhecido."""
    rows = _callbacks(records, tenant)
    final = [r for r in rows if r["status"] in {"concluido", "cancelado", "esgotado"}]
    completed = sum(r["status"] == "concluido" for r in final)
    return {"completed": completed, "finalized": len(final),
            "completion_percent": percent(completed, len(final))}


def callback_attempt_distribution(records, tenant):
    """63. Contagem dos pedidos por 0, 1 ou 2 tentativas documentadas."""
    counts = Counter(row["attempts"] for row in _callbacks(records, tenant))
    return {str(n): counts[n] for n in range(MAX_ATTEMPTS + 1)}


def callback_pending_per_day(records, tenant):
    """64. Pendências por dia UTC em que o pedido foi criado."""
    counts = Counter()
    for row in _callbacks(records, tenant):
        if row["status"] == "pendente":
            day = datetime.fromtimestamp(row["at"], tz=timezone.utc).date().isoformat()
            counts[day] += 1
    return dict(sorted(counts.items()))


def callback_pending_retry_pool(records, tenant):
    """65. Volume elegível por tentativas; não agenda nem executa chamada."""
    rows = [r for r in _callbacks(records, tenant) if r["status"] == "pendente"]
    first = sum(r["attempts"] == 0 for r in rows)
    retry = sum(0 < r["attempts"] < MAX_ATTEMPTS for r in rows)
    exhausted = sum(r["attempts"] >= MAX_ATTEMPTS for r in rows)
    return {"pending": len(rows), "first_attempt": first,
            "retry_candidate": retry, "requires_review": exhausted}
