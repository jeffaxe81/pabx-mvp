"""Cinco visões locais de desempenho de CDR por ramal técnico (86-90).

CDR não prova tempo de espera em fila nem produtividade de um atendente
humano. Não inferir penalidades dos contadores; não expor CallerID.
"""
from collections import defaultdict
from statistics import median

from insights_calls import _calls
from insights_calls_advanced import _operator
from insights_calls_audit import RECOGNIZED
from insights_common import percent, valid_seconds


def _agent_groups(records, tenant):
    groups = defaultdict(lambda: {"known": 0, "answered": 0,
                                  "not_answered": 0, "durations": []})
    for row in _calls(records, tenant):
        if row["disposition"] not in RECOGNIZED:
            continue
        agent = _operator(row, tenant)
        if agent is None:
            continue
        group = groups[agent]
        group["known"] += 1
        if row["disposition"] == "ANSWERED":
            group["answered"] += 1
            seconds = valid_seconds(row.get("billable_seconds"))
            if seconds is not None:
                group["durations"].append(seconds)
        else:
            group["not_answered"] += 1
    return groups


def agent_answer_rate(records, tenant):
    """86. Taxa de ANSWERED entre CDR identificáveis por ramal."""
    return {agent: {"answered": row["answered"], "known_cdr": row["known"],
                    "answered_percent": percent(row["answered"], row["known"])}
            for agent, row in sorted(_agent_groups(records, tenant).items())}


def agent_nonanswered_volume(records, tenant):
    """87. Volume de CDR não atendidos reconhecidos por ramal."""
    return {agent: row["not_answered"]
            for agent, row in sorted(_agent_groups(records, tenant).items())}


def agent_mean_talk_seconds(records, tenant):
    """88. Duração média faturável das atendidas com valor confiável."""
    out = {}
    for agent, row in sorted(_agent_groups(records, tenant).items()):
        values = row["durations"]
        out[agent] = {"calls_measured": len(values),
                      "average_seconds": round(sum(values) / len(values), 1)
                      if values else None}
    return out


def agent_median_talk_seconds(records, tenant):
    """89. Mediana da duração válida; None se não houver medida."""
    out = {}
    for agent, row in sorted(_agent_groups(records, tenant).items()):
        values = row["durations"]
        out[agent] = {"calls_measured": len(values),
                      "median_seconds": round(median(values), 1) if values else None}
    return out


def agent_duration_coverage(records, tenant):
    """91. Cobertura dos CDR ANSWERED com duração faturável confiável.

    Uma duração desconhecida não deve ser interpretada como zero segundo.
    """
    return {agent: {
        "answered": row["answered"],
        "with_valid_duration": len(row["durations"]),
        "without_valid_duration": row["answered"] - len(row["durations"]),
        "coverage_percent": percent(len(row["durations"]), row["answered"]),
    } for agent, row in sorted(_agent_groups(records, tenant).items())}


def agent_over_five_minutes(records, tenant):
    """90. Contagem de chamadas atendidas acima de cinco minutos."""
    out = {}
    for agent, row in sorted(_agent_groups(records, tenant).items()):
        values = row["durations"]
        long_calls = sum(value > 300 for value in values)
        out[agent] = {"calls_measured": len(values), "over_300_seconds": long_calls,
                      "over_300_seconds_percent": percent(long_calls, len(values))}
    return out
