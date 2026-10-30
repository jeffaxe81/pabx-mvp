"""Cinco indicadores locais de CDR não atendido (66-70), por tenant.

CDR com Disposition não-ANSWERED NÃO é prova de abandono de fila.
A fonte é o JSONL de chamadas; sem CallerID, nomes ou mídia na saída.
"""
from collections import Counter, defaultdict

from insights_calls import _calls
from insights_calls_advanced import _operator
from insights_common import percent, valid_day

NONANSWER = {"NOANSWER", "NO ANSWER", "BUSY", "CANCEL", "CANCELLED",
             "CONGESTION", "FAILED", "CHANUNAVAIL"}
KNOWN = NONANSWER | {"ANSWERED"}


def _unanswered(records, tenant):
    return [r for r in _calls(records, tenant) if r["disposition"] in NONANSWER]


def unanswered_reason_counts(records, tenant):
    """66. CDR não atendidos classificados por disposição reconhecida."""
    counts = Counter(r["disposition"] for r in _unanswered(records, tenant))
    return {key: counts[key] for key in sorted(NONANSWER)}


def unanswered_daily_volume(records, tenant):
    """67. Volume não atendido por dia de CDR válido."""
    counts = Counter()
    for row in _unanswered(records, tenant):
        day = valid_day(row.get("date"))
        if day is not None:
            counts[day] += 1
    return dict(sorted(counts.items()))


def unanswered_by_agent(records, tenant):
    """68. Não atendidas associadas a ramal válido; não representa culpa."""
    counts = Counter()
    for row in _unanswered(records, tenant):
        agent = _operator(row, tenant)
        if agent is not None:
            counts[agent] += 1
    return dict(sorted(counts.items()))


def unanswered_monthly_volume(records, tenant):
    """69. Volume por mês do CDR, sem inferir horário da chamada."""
    counts = Counter()
    for row in _unanswered(records, tenant):
        day = valid_day(row.get("date"))
        if day is not None:
            counts[day[:7]] += 1
    return dict(sorted(counts.items()))


def unanswered_daily_rate(records, tenant):
    """70. Percentual não atendido entre CDRs reconhecidos de cada dia."""
    counts = defaultdict(lambda: [0, 0])
    for row in _calls(records, tenant):
        if row["disposition"] not in KNOWN:
            continue
        day = valid_day(row.get("date"))
        if day is None:
            continue
        counts[day][1] += 1
        counts[day][0] += row["disposition"] in NONANSWER
    return {day: {"not_answered": n, "known_cdr": total,
                  "not_answered_percent": percent(n, total)}
            for day, (n, total) in sorted(counts.items())}
