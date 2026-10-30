"""Cinco análises inéditas de chamadas por operador e duração.

Escopo apenas local. Nunca usa dados sem tenant explícito nem publica
números de clientes.
"""
from collections import Counter, defaultdict

from insights_calls import _calls
from insights_common import AGENT_RE, valid_seconds


def _operator(row, tenant):
    agent = row.get("operator")
    match = AGENT_RE.fullmatch(agent) if isinstance(agent, str) else None
    return agent if match and match.group(1) == tenant else None


def calls_disposition_breakdown(records, tenant):
    """21. Distribuição das chamadas por resultado CDR."""
    counts = Counter(r["disposition"] for r in _calls(records, tenant))
    return dict(sorted(counts.items()))


def calls_volume_by_agent(records, tenant):
    """22. Quantidade de chamadas associadas a cada atendente."""
    counts = Counter()
    for row in _calls(records, tenant):
        agent = _operator(row, tenant)
        if agent is not None:
            counts[agent] += 1
    return dict(sorted(counts.items()))


def calls_answered_by_agent(records, tenant):
    """23. Ligações atendidas por atendente identificado."""
    counts = Counter()
    for row in _calls(records, tenant):
        agent = _operator(row, tenant)
        if agent and row["disposition"] == "ANSWERED":
            counts[agent] += 1
    return dict(sorted(counts.items()))


def calls_talk_time_by_agent(records, tenant):
    """24. Tempo total falado por atendente, descartando durações inválidas."""
    totals = defaultdict(float)
    for row in _calls(records, tenant):
        agent = _operator(row, tenant)
        duration = valid_seconds(row.get("billable_seconds"))
        if agent and row["disposition"] == "ANSWERED" and duration is not None:
            totals[agent] += duration
    return {agent: round(total, 1) for agent, total in sorted(totals.items())}


def calls_duration_bands(records, tenant):
    """25. Faixas de duração: 0-30, 31-120, 121-300 e mais de 300 segundos."""
    out = {"0_30": 0, "31_120": 0, "121_300": 0, "over_300": 0}
    for row in _calls(records, tenant):
        if row["disposition"] != "ANSWERED":
            continue
        seconds = valid_seconds(row.get("billable_seconds"))
        if seconds is None:
            continue
        band = "0_30" if seconds <= 30 else ("31_120" if seconds <= 120 else
                                            "121_300" if seconds <= 300 else "over_300")
        out[band] += 1
    return out
