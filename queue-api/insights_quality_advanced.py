"""Indicadores locais 91–95 de qualidade RTCP exportada, por tenant.

Não substituem monitoramento ativo: somente amostras disponíveis, sem mídia,
telefones, identificação de clientes ou comunicação com Asterisk.
"""
from collections import defaultdict
from math import ceil

from insights_common import percent
from insights_quality_export import _quality


def _percentile_95(values):
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(0, ceil(len(ordered) * .95) - 1)], 2)


def quality_p95_jitter(records, tenant):
    """91. Percentil 95 de jitter RTCP (ms) em amostras medidas."""
    values = [r["jitter"] for r in _quality(records, tenant)
              if r["jitter"] is not None]
    return {"samples": len(values), "p95_jitter_ms": _percentile_95(values)}


def quality_p95_rtt(records, tenant):
    """92. Percentil 95 de RTT RTCP (ms) em amostras medidas."""
    values = [r["rtt"] for r in _quality(records, tenant)
              if r["rtt"] is not None]
    return {"samples": len(values), "p95_rtt_ms": _percentile_95(values)}


def quality_high_loss_rate(records, tenant):
    """93. Proporção de perda superior a 3% entre amostras com perda."""
    values = [r["loss"] for r in _quality(records, tenant)
              if r["loss"] is not None]
    high = sum(value > 3 for value in values)
    return {"samples": len(values), "above_three_percent": high,
            "rate_percent": percent(high, len(values))}


def quality_metric_coverage(records, tenant):
    """94. Quantos snapshots trazem cada campo RTCP medido."""
    rows = _quality(records, tenant)
    return {"snapshots_with_any_metric": len(rows),
            "jitter_measured": sum(r["jitter"] is not None for r in rows),
            "loss_measured": sum(r["loss"] is not None for r in rows),
            "rtt_measured": sum(r["rtt"] is not None for r in rows),
            "all_three_measured": sum(all(r[k] is not None for k in
                                           ("jitter", "loss", "rtt")) for r in rows)}


def quality_worst_agent_sample_rate(records, tenant):
    """95. Maior fração de amostras ruins, mínimo de 3 por ramal.

    Não identifica a causa e não significa mau desempenho individual.
    """
    groups = defaultdict(lambda: [0, 0])
    for row in _quality(records, tenant):
        if row["jitter"] is None and row["loss"] is None:
            continue
        item = groups[row["agent"]]
        item[0] += 1
        item[1] += bool((row["jitter"] is not None and row["jitter"] > 30)
                        or (row["loss"] is not None and row["loss"] > 3))
    eligible = {agent: v for agent, v in groups.items() if v[0] >= 3}
    if not eligible:
        return {"agent": None, "samples": 0, "poor": 0, "poor_percent": None}
    agent = min(eligible, key=lambda k: (-eligible[k][1] / eligible[k][0], k))
    samples, poor = eligible[agent]
    return {"agent": agent, "samples": samples, "poor": poor,
            "poor_percent": percent(poor, samples)}
