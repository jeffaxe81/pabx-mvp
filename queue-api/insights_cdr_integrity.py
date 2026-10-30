"""Indicadores 96–100 de integridade de CDR com tenant isolado.

São diagnósticos de snapshots locais; não alteram o registro nem expõem PII.
"""
from collections import Counter

from insights_calls import _calls
from insights_calls_advanced import _operator
from insights_calls_audit import RECOGNIZED
from insights_common import percent, tenant_rows, valid_day, valid_seconds


def cdr_unknown_status_by_day(records, tenant):
    """96. Registros CDR com disposição desconhecida por data válida."""
    totals = Counter()
    for row in _calls(records, tenant):
        day = valid_day(row.get("date"))
        if day is not None and row["disposition"] not in RECOGNIZED:
            totals[day] += 1
    return dict(sorted(totals.items()))


def cdr_answered_zero_duration(records, tenant):
    """97. ANSWERED com billable_seconds conhecido igual a zero."""
    rows = [r for r in _calls(records, tenant) if r["disposition"] == "ANSWERED"]
    known = [v for r in rows for v in [valid_seconds(r.get("billable_seconds"))]
             if v is not None]
    return {"answered": len(rows), "with_valid_duration": len(known),
            "zero_seconds": sum(v == 0 for v in known)}


def cdr_nonanswered_with_billable(records, tenant):
    """98. CDRs não atendidos que trazem tempo faturável positivo."""
    rows = [r for r in _calls(records, tenant)
            if r["disposition"] in RECOGNIZED and r["disposition"] != "ANSWERED"]
    count = sum((v is not None and v > 0)
                for r in rows
                for v in [valid_seconds(r.get("billable_seconds"))])
    return {"nonanswered_known": len(rows), "positive_billable_seconds": count}


def cdr_answered_missing_operator_rate(records, tenant):
    """99. Taxa de CDR ANSWERED sem operador técnico atribuível."""
    rows = [r for r in _calls(records, tenant) if r["disposition"] == "ANSWERED"]
    missing = sum(_operator(row, tenant) is None for row in rows)
    return {"answered": len(rows), "without_attributable_operator": missing,
            "rate_percent": percent(missing, len(rows))}


def cdr_invalid_disposition_structure(records, tenant):
    """100. Entradas do tenant com disposition vazio/tipo inválido/excessivo."""
    rows = tenant_rows(records, tenant)
    invalid = sum(not isinstance(r.get("disposition"), str)
                  or not 0 < len(r["disposition"]) <= 32 for r in rows)
    return {"tenant_records": len(rows), "invalid_disposition": invalid}
