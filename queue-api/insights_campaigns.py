"""Cinco resumos de campanhas locais, sem números de telefone na saída."""
from collections import Counter, defaultdict

from insights_common import AGENT_RE, percent, tenant_rows

KNOWN_STATUSES = {
    "pendente", "discando", "atendida", "ocupado",
    "sem_resposta", "cancelada", "falha", "esgotado",
}
MAX_ATTEMPTS = 3


def _campaigns(records, tenant):
    campaigns = []
    for campaign in tenant_rows(records, tenant):
        agent = campaign.get("agent_extension")
        match = AGENT_RE.fullmatch(agent) if isinstance(agent, str) else None
        if not match or match.group(1) != tenant:
            continue
        contacts = campaign.get("contacts")
        if not isinstance(contacts, list) or len(contacts) > 1000:
            continue
        filtered = [
            {"status": item["status"], "attempts": item["attempts"]}
            for item in contacts if isinstance(item, dict)
            and isinstance(item.get("status"), str)
            and item["status"] in KNOWN_STATUSES
            and type(item.get("attempts")) is int
            and 0 <= item["attempts"] <= MAX_ATTEMPTS
        ]
        campaigns.append({"agent": agent, "contacts": filtered})
    return campaigns


def campaign_status_breakdown(records, tenant):
    """16. Quantidade de contatos em cada estado, sem discagem."""
    counts = Counter()
    for campaign in _campaigns(records, tenant):
        counts.update(item["status"] for item in campaign["contacts"])
    return {status: counts[status] for status in sorted(KNOWN_STATUSES)}


def campaign_completion_rate(records, tenant):
    """17. Proporção de contatos finalizados (não pendentes/discando)."""
    contacts = [
        c for campaign in _campaigns(records, tenant) for c in campaign["contacts"]
    ]
    finished = sum(c["status"] not in {"pendente", "discando"} for c in contacts)
    return {"finished": finished, "total": len(contacts),
            "finished_rate_percent": percent(finished, len(contacts))}


def campaign_retry_pool(records, tenant):
    """18. Contagem de candidatos à nova tentativa, sem iniciar chamada."""
    contacts = [
        c for campaign in _campaigns(records, tenant) for c in campaign["contacts"]
    ]
    return {
        "first_attempt_pending": sum(
            c["status"] == "pendente" and c["attempts"] == 0 for c in contacts
        ),
        "retry_pending": sum(
            c["status"] == "pendente" and 0 < c["attempts"] < MAX_ATTEMPTS
            for c in contacts
        ),
        "exhausted_attempt_budget": sum(
            c["attempts"] >= MAX_ATTEMPTS and c["status"] != "atendida"
            for c in contacts
        ),
    }


def campaign_attempts_summary(records, tenant):
    """19. Média e total de tentativas registradas por contato."""
    attempts = [
        c["attempts"] for campaign in _campaigns(records, tenant)
        for c in campaign["contacts"]
    ]
    return {"contacts": len(attempts), "attempts": sum(attempts),
            "average_attempts": round(sum(attempts) / len(attempts), 2) if attempts else None}


def campaign_agent_workload(records, tenant):
    """20. Distribuição de contatos e tentativas por ramal operador."""
    data = defaultdict(lambda: {"campaigns": 0, "contacts": 0, "attempts": 0})
    for campaign in _campaigns(records, tenant):
        entry = data[campaign["agent"]]
        entry["campaigns"] += 1
        entry["contacts"] += len(campaign["contacts"])
        entry["attempts"] += sum(c["attempts"] for c in campaign["contacts"])
    return dict(sorted(data.items()))
