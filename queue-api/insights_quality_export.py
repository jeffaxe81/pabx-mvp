"""Cinco indicadores de exportações locais de qualidade RTCP/QualityLog.

Entrada em JSON array exportado de forma autorizada do QualityLog em
memória. A CLI NÃO gera registros de mídia nem consulta o Asterisk.
"""
from collections import defaultdict
import re

from insights_common import percent, require_tenant
from quality_monitoring import _parse_float_or_none, _parse_loss_percent

CHANNEL = re.compile(r"PJSIP/(t[1-9][0-9]*-[a-z0-9_-]{1,75})-[A-Fa-f0-9]{1,16}\Z")


def _quality(records, tenant):
    require_tenant(tenant)
    if not isinstance(records, list) or len(records) > 20000:
        raise ValueError("exportação RTCP inválida")
    selected = []
    for row in records:
        if not isinstance(row, dict):
            continue
        channel = row.get("channel")
        match = CHANNEL.fullmatch(channel) if isinstance(channel, str) else None
        if not match or match.group(1).split("-", 1)[0] != tenant:
            continue
        jitter = _parse_float_or_none(row.get("jitter_ms"))
        loss = _parse_loss_percent(row.get("packet_loss_percent"))
        rtt = _parse_float_or_none(row.get("rtt_ms"))
        if jitter is None and loss is None and rtt is None:
            continue
        selected.append({"agent": match.group(1), "jitter": jitter,
                         "loss": loss, "rtt": rtt})
    return selected


def quality_average_jitter(records, tenant):
    """56. Jitter médio dos registros que realmente têm medida."""
    values = [r["jitter"] for r in _quality(records, tenant) if r["jitter"] is not None]
    return {"samples": len(values),
            "average_jitter_ms": round(sum(values) / len(values), 2) if values else None}


def quality_jitter_high_rate(records, tenant):
    """57. Taxa de jitter acima do limiar de referência de 30 ms."""
    values = [r["jitter"] for r in _quality(records, tenant) if r["jitter"] is not None]
    high = sum(v > 30 for v in values)
    return {"high": high, "samples": len(values),
            "above_30ms_percent": percent(high, len(values))}


def quality_average_packet_loss(records, tenant):
    """58. Perda percentual média observada onde houver dados."""
    values = [r["loss"] for r in _quality(records, tenant) if r["loss"] is not None]
    return {"samples": len(values),
            "average_packet_loss_percent": round(sum(values) / len(values), 2) if values else None}


def quality_average_rtt(records, tenant):
    """59. RTT médio dos registros exportados."""
    values = [r["rtt"] for r in _quality(records, tenant) if r["rtt"] is not None]
    return {"samples": len(values),
            "average_rtt_ms": round(sum(values) / len(values), 2) if values else None}


def quality_poor_by_agent(records, tenant):
    """60. Amostras com jitter >30 ms ou perda >3% agrupadas por ramal."""
    groups = defaultdict(lambda: {"measured": 0, "poor": 0})
    for row in _quality(records, tenant):
        if row["jitter"] is None and row["loss"] is None:
            continue
        entry = groups[row["agent"]]
        entry["measured"] += 1
        entry["poor"] += ((row["jitter"] is not None and row["jitter"] > 30)
                          or (row["loss"] is not None and row["loss"] > 3))
    return {agent: {"measured": stat["measured"], "poor": stat["poor"],
                    "poor_percent": percent(stat["poor"], stat["measured"])}
            for agent, stat in sorted(groups.items())}
