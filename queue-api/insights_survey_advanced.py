"""Cinco indicadores avançados de satisfação com escopo restrito ao tenant."""
from collections import defaultdict
from datetime import date
from statistics import median

from insights_common import AGENT_RE, percent, valid_day
from insights_survey import _surveys


def survey_median_score(records, tenant):
    """36. Mediana de satisfação, sem preencher amostra ausente."""
    scores = [row["score"] for row in _surveys(records, tenant)]
    return round(median(scores), 1) if scores else None


def survey_score_by_agent(records, tenant):
    """37. Média e amostra por agente que pertence exatamente ao tenant."""
    groups = defaultdict(list)
    for row in _surveys(records, tenant):
        agent = row.get("operator")
        matched = AGENT_RE.fullmatch(agent) if isinstance(agent, str) else None
        if matched and matched.group(1) == tenant:
            groups[agent].append(row["score"])
    return {agent: {"responses": len(values), "average": round(sum(values) / len(values), 2)}
            for agent, values in sorted(groups.items())}


def survey_neutral_rate(records, tenant):
    """38. Percentual de respostas neutras (nota 3)."""
    rows = _surveys(records, tenant)
    neutral = sum(r["score"] == 3 for r in rows)
    return {"neutral": neutral, "responses": len(rows),
            "neutral_percent": percent(neutral, len(rows))}


def survey_weekly_response_count(records, tenant):
    """39. Quantidade de respostas por semana ISO."""
    groups = defaultdict(int)
    for row in _surveys(records, tenant):
        day = valid_day(row.get("date"))
        if day:
            iso = date.fromisoformat(day).isocalendar()
            groups[f"{iso.year}-W{iso.week:02d}"] += 1
    return dict(sorted(groups.items()))


def survey_monthly_average(records, tenant):
    """40. Evolução mensal da nota média e tamanho da amostra."""
    groups = defaultdict(list)
    for row in _surveys(records, tenant):
        day = valid_day(row.get("date"))
        if day:
            groups[day[:7]].append(row["score"])
    return {month: {"responses": len(values), "average": round(sum(values) / len(values), 2)}
            for month, values in sorted(groups.items())}
