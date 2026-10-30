"""Cinco indicadores avançados de campanhas, sem executar chamadas."""
from collections import defaultdict

from insights_campaigns import _campaigns
from insights_common import percent


def _contacts(records, tenant):
    return [c for campaign in _campaigns(records, tenant) for c in campaign["contacts"]]


def campaigns_answered_share(records, tenant):
    """46. Percentual de contatos com ligação atendida."""
    rows = _contacts(records, tenant)
    count = sum(c["status"] == "atendida" for c in rows)
    return {"answered": count, "contacts": len(rows),
            "answered_percent": percent(count, len(rows))}


def campaigns_busy_share(records, tenant):
    """47. Percentual de contatos com último status ocupado."""
    rows = _contacts(records, tenant)
    count = sum(c["status"] == "ocupado" for c in rows)
    return {"busy": count, "contacts": len(rows),
            "busy_percent": percent(count, len(rows))}


def campaigns_no_answer_share(records, tenant):
    """48. Percentual de contatos com status sem resposta."""
    rows = _contacts(records, tenant)
    count = sum(c["status"] == "sem_resposta" for c in rows)
    return {"no_answer": count, "contacts": len(rows),
            "no_answer_percent": percent(count, len(rows))}


def campaigns_in_progress_count(records, tenant):
    """49. Quantidade de contatos marcados como discando."""
    return sum(c["status"] == "discando" for c in _contacts(records, tenant))


def campaigns_answered_by_agent(records, tenant):
    """50. Contatos atendidos e taxa por operador (sem números)."""
    groups = defaultdict(lambda: {"answered": 0, "total": 0})
    for campaign in _campaigns(records, tenant):
        agent = campaign["agent"]
        for c in campaign["contacts"]:
            groups[agent]["total"] += 1
            groups[agent]["answered"] += c["status"] == "atendida"
    return {
        agent: {"answered": value["answered"], "total": value["total"],
                "answered_percent": percent(value["answered"], value["total"])}
        for agent, value in sorted(groups.items())
    }
