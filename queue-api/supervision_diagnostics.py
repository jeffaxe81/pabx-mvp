"""20 verificações operacionais conservadoras para a supervisão do AXE PABX.

Entrada: exclusivamente o resumo por empresa já autenticado no server.
Os limites são REFERÊNCIAS de diagnóstico, não SLA contratual.
Não aciona AMI, não bloqueia chamadas e não autoriza GO de produção.
"""
import math

# id, grupo, campo, regra, limiar, denominador, mínimo de amostra
# Cada regra é uma capacidade operacional identificável e rastreável.
RULES = (
    ("OP-01", "queues", "waiting_calls", "gte", 10, None, 0),
    ("OP-02", "queues", "queues_with_waiting", "gte", 3, None, 0),
    ("OP-03", "queues", "waiting_above_sla_threshold", "gte", 3, None, 0),
    ("OP-04", "queues", "waiting_over_60_seconds", "gte", 1, None, 0),
    ("OP-05", "queues", "longest_wait_seconds", "gte", 180, None, 0),
    ("OP-06", "extensions", "monitored_extensions", "zero", 0, None, 0),
    ("OP-07", "extensions", "free_extensions", "zero", 0, "monitored_extensions", 1),
    ("OP-08", "extensions", "ringing_extensions", "gte", 5, None, 0),
    ("OP-09", "extensions", "busy_extensions", "ratio_gte", 80, "monitored_extensions", 5),
    ("OP-10", "extensions", "unavailable_extensions", "gte", 3, None, 0),
    ("OP-11", "sla", "offered_calls", "sample", 0, None, 0),
    ("OP-12", "sla", "weighted_sla_percent", "lt", 80, "offered_calls", 10),
    ("OP-13", "sla", "outside_sla_calls", "gte", 10, "offered_calls", 1),
    ("OP-14", "sla", "queues_below_reference_80", "gte", 2, "offered_calls", 1),
    ("OP-15", "sla", "outside_sla_calls", "ratio_gte", 30, "offered_calls", 10),
    ("OP-16", "observations", "missed_events_in_buffer", "gte", 10, None, 0),
    ("OP-17", "observations", "fraud_alerts_in_buffer", "gte", 1, None, 0),
    ("OP-18", "observations", "poor_quality_samples_in_buffer", "gte", 3, None, 0),
    ("OP-19", "observations", "paused_agents_snapshot", "gte", 5, None, 0),
    ("OP-20", "observations", "manual_absent_overrides", "gte", 5, None, 0),
)


def _valid_number(value):
    """Rejeita bool, NaN, infinito e números negativos em observações."""
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 100_000_000


def evaluate_supervision_diagnostics(summary):
    """Produz 20 situações isoladas: normal, attention ou unknown.

    Sem amostra, nenhuma regra de desempenho poderá concluir "normal".
    Falha de esquema recusa todo o processamento, não gera falso verde.
    """
    if (not isinstance(summary, dict)
            or summary.get("scope") != "memory_snapshot_tenant_only"
            or summary.get("metric_count") != 20
            or not isinstance(summary.get("tenant"), str)):
        raise ValueError("resumo de supervisao invalido")
    sections = {}
    for group in ("queues", "extensions", "sla", "observations"):
        section = summary.get(group)
        if not isinstance(section, dict):
            raise ValueError("secao de supervisao invalida")
        sections[group] = section

    output = []
    for rule_id, group, metric, kind, threshold, denominator_key, minimum in RULES:
        section = sections[group]
        measured = section.get(metric)
        denominator = section.get(denominator_key) if denominator_key else None
        # Métricas nulas/ausentes não podem ser avaliadas como saudáveis.
        if measured is None or not _valid_number(measured):
            status = "unknown"
        elif denominator_key and (not _valid_number(denominator)
                                  or denominator < minimum):
            status = "unknown"
        elif kind == "sample":
            status = "normal" if measured > 0 else "unknown"
        elif kind == "zero":
            status = "attention" if measured == 0 else "normal"
        elif kind == "gte":
            status = "attention" if measured >= threshold else "normal"
        elif kind == "lt":
            status = "attention" if measured < threshold else "normal"
        elif kind == "ratio_gte":
            status = ("attention" if denominator > 0 and
                      measured * 100 >= threshold * denominator else "normal")
        else:
            raise ValueError("regra desconhecida")
        output.append({
            "rule_id": rule_id, "section": group, "metric": metric,
            "status": status, "observed": measured if _valid_number(measured) else None,
            "reference": threshold, "reference_is_contractual": False,
        })
    attention = sum(row["status"] == "attention" for row in output)
    unknown = sum(row["status"] == "unknown" for row in output)
    return {
        "schema_version": 1,
        "tenant": summary["tenant"],
        "evaluation": "reference_only_not_automatic_remediation",
        "rule_count": 20, "attention_count": attention,
        "unknown_count": unknown, "normal_count": 20 - attention - unknown,
        "rules": output, "operational_homologation_claimed": False,
    }
