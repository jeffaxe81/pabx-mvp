"""Resumo de supervisão por empresa: 20 indicadores operacionais (5 por área).

Somente fontes em memória do backend. Isolamento por tenant aplicado
independentemente dos filtros do chamador; nunca retorna CallerID,
telefones, canais, nomes, notas, mensagens nem credenciais.

A autorização é feita pelo handler HTTP antes de chamar este módulo.
O snapshot não é prova de integridade do fluxo real no ambiente do cliente.
"""
from collections import Counter
from math import isfinite
import time

from insights_common import percent, require_tenant
from monitoring_access import extension_tenant, scoped_monitoring_entries
from pickup import queue_tenant


def _safe_count(value):
    return value if type(value) is int and 0 <= value <= 10_000_000 else 0


def _safe_wait(value):
    return value if type(value) in (int, float) and isfinite(value) and 0 <= value <= 86400 * 30 else None


def build_supervision_summary(tenant, *, waiting, extensions, sla, missed,
                              fraud, quality, pauses, presence,
                              threshold_seconds=20):
    """Agrega 20 indicadores sem dados identificáveis ou efeitos colaterais."""
    require_tenant(tenant)
    if type(threshold_seconds) is not int or not 0 <= threshold_seconds <= 3600:
        raise ValueError("limiar SLA invalido")
    if not isinstance(waiting, list) or not isinstance(extensions, list):
        raise ValueError("snapshots invalidos")
    if not isinstance(sla, dict) or not isinstance(pauses, dict) or not isinstance(presence, dict):
        raise ValueError("snapshots invalidos")

    # 1-5: fila. O identificador do canal e a BINA nunca são expostos.
    qrows = [row for row in waiting if isinstance(row, dict)
             and queue_tenant(row.get("queue")) == tenant]
    waits = [_safe_wait(row.get("waiting_seconds")) for row in qrows]
    measured = [w for w in waits if w is not None]
    queue_stats = {
        "waiting_calls": len(qrows),                                   # 01
        "queues_with_waiting": len({row["queue"] for row in qrows}),    # 02
        "waiting_above_sla_threshold": sum(w > threshold_seconds for w in measured), # 03
        "waiting_over_60_seconds": sum(w > 60 for w in measured),      # 04
        "longest_wait_seconds": round(max(measured), 1) if measured else None,       # 05
    }

    # 6-10: BLF do contexto da empresa; estados manuais não são status SIP.
    erows = [row for row in extensions if isinstance(row, dict)
             and row.get("context") == tenant + "-hints"
             and (extension_tenant(row.get("exten")) in (None, tenant))
             and isinstance(row.get("exten"), str)]
    counts = Counter(row.get("status_label") for row in erows
                     if isinstance(row.get("status_label"), str))
    extension_stats = {
        "monitored_extensions": len(erows),                            # 06
        "free_extensions": counts["livre"],                           # 07
        "ringing_extensions": counts["tocando"],                       # 08
        "busy_extensions": counts["em uso"] + counts["ocupado"],       # 09
        "unavailable_extensions": counts["indisponível"],             # 10
    }

    # 11-15: SLA da janela do tracker; não é o histórico persistido.
    observed = []
    for queue, row in sla.items():
        if queue_tenant(queue) != tenant or not isinstance(row, dict):
            continue
        offered = _safe_count(row.get("offered"))
        within = _safe_count(row.get("within_sla"))
        if offered > 0 and within <= offered:
            observed.append((offered, within))
    total_offered = sum(o for o, _ in observed)
    total_within = sum(w for _, w in observed)
    sla_stats = {
        "offered_calls": total_offered,                              # 11
        "within_sla_calls": total_within,                            # 12
        "outside_sla_calls": total_offered - total_within,           # 13
        "weighted_sla_percent": percent(total_within, total_offered) if total_offered else None, # 14
        "queues_below_reference_80": sum(w * 5 < o * 4 for o, w in observed),       # 15
    }

    # 16-20: observações limitadas aos buffers existentes; não representa
    # histórico ilimitado nem incidentes confirmados. Contar apenas
    # eventos previamente atribuídos de forma inequívoca a esta empresa.
    missed_rows = scoped_monitoring_entries(missed, tenant)
    fraud_rows = scoped_monitoring_entries(fraud, tenant)
    quality_rows = scoped_monitoring_entries(quality, tenant)
    paused = sum(1 for extension, entry in pauses.items()
                 if extension_tenant(extension) == tenant
                 and isinstance(entry, dict) and entry.get("paused") is True)
    manual_absent = sum(1 for extension, entry in presence.items()
                        if extension_tenant(extension) == tenant
                        and isinstance(entry, dict) and entry.get("status") == "ausente")
    observations = {
        "missed_events_in_buffer": len(missed_rows),                 # 16
        "fraud_alerts_in_buffer": len(fraud_rows),                   # 17
        "poor_quality_samples_in_buffer": sum(
            row.get("poor") is True for row in quality_rows),       # 18
        "paused_agents_snapshot": paused,                           # 19
        "manual_absent_overrides": manual_absent,                    # 20
    }
    return {
        "schema_version": 1,
        "tenant": tenant,
        "scope": "memory_snapshot_tenant_only",
        "measured_at_epoch_seconds": int(time.time()),
        "snapshot_not_operational_homologation": True,
        "reference_sla_percent": 80,
        "sla_threshold_seconds": threshold_seconds,
        "metric_count": 20,
        "queues": queue_stats,
        "extensions": extension_stats,
        "sla": sla_stats,
        "observations": observations,
    }
