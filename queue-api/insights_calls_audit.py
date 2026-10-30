"""Auditoria de qualidade de dados do CDR, cinco indicadores sem PII."""
from insights_calls import _calls
from insights_common import AGENT_RE, valid_day, valid_seconds

RECOGNIZED = {"ANSWERED", "NOANSWER", "NO ANSWER", "BUSY", "CANCEL",
              "CANCELLED", "CONGESTION", "FAILED", "CHANUNAVAIL"}


def calls_invalid_date_count(records, tenant):
    """31. Registros de chamadas com dia inexistente ou sem data."""
    return sum(valid_day(r.get("date")) is None for r in _calls(records, tenant))


def calls_missing_answered_duration(records, tenant):
    """32. Chamadas atendidas sem duração faturável válida."""
    return sum(r["disposition"] == "ANSWERED"
               and valid_seconds(r.get("billable_seconds")) is None
               for r in _calls(records, tenant))


def calls_unknown_disposition_count(records, tenant):
    """33. Resultados CDR não reconhecidos pela nomenclatura conhecida."""
    return sum(r["disposition"] not in RECOGNIZED for r in _calls(records, tenant))


def calls_missing_operator_count(records, tenant):
    """34. Chamadas atendidas sem atendente atribuível com segurança."""
    def valid_agent(row):
        agent = row.get("operator")
        match = AGENT_RE.fullmatch(agent) if isinstance(agent, str) else None
        return bool(match and match.group(1) == tenant)
    return sum(r["disposition"] == "ANSWERED" and not valid_agent(r)
               for r in _calls(records, tenant))


def calls_negative_duration_conflicts(records, tenant):
    """35. Durações negativas, bool ou não numéricas nos CDR disponíveis."""
    return sum(
        r.get("billable_seconds") is not None
        and valid_seconds(r.get("billable_seconds")) is None
        for r in _calls(records, tenant)
    )
