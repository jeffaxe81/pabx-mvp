"""
Relatórios históricos por atendente/tenant/período, a partir dos
mesmos eventos CDR já usados pelas métricas do dia (manual 13) - mas
aqui cada chamada vira um REGISTRO persistido (JSONL, um json por
linha), não só um contador que zera à meia-noite.

Lógica pura de parsing/agregação aqui; leitura/escrita em disco fica
isolada em CallLogStore pra facilitar teste com arquivos temporários.
"""
import json
import re
import time
from pathlib import Path

OPERATOR_RE = re.compile(r"^PJSIP/([a-zA-Z0-9_-]+)-[0-9a-fA-F]+$")
TENANT_RE = re.compile(r"^(t[1-9][0-9]*)-")
_CDR_ID = re.compile(r"^[A-Za-z0-9._-]{1,96}$")
_MAX_REPORT_LINE = 16384


def extract_operator(channel: str):
    """'PJSIP/t1-recepcao-00000003' -> 't1-recepcao'. None se não bater o padrão."""
    if not isinstance(channel, str):
        return None
    match = OPERATOR_RE.fullmatch(channel)
    return match.group(1) if match else None


def extract_tenant(operator: str, context: str):
    """Tenta primeiro pelo prefixo do operador, depois pelo contexto."""
    for candidate in (operator, context):
        if isinstance(candidate, str):
            match = TENANT_RE.match(candidate)
            if match:
                return match.group(1)
    return None


def parse_cdr_for_report(event: dict):
    """
    Transforma um evento AMI 'Cdr' num registro de relatório, ou
    retorna None se o evento não servir (não é Cdr, ou sem disposition).
    """
    if not isinstance(event, dict) or event.get("Event") != "Cdr":
        return None

    disposition = event.get("Disposition")
    if (not isinstance(disposition, str) or not disposition.isprintable()
            or not 1 <= len(disposition) <= 32):
        return None
    identifiers = [event[key] for key in ("UniqueID", "Uniqueid") if key in event]
    if identifiers and (
            any(not isinstance(identifier, str)
                or _CDR_ID.fullmatch(identifier) is None for identifier in identifiers)
            or len(set(identifiers)) != 1):
        return None

    channel = event.get("DestinationChannel") or event.get("Channel") or ""
    operator = extract_operator(channel)
    # Nunca atribuir CDR a uma empresa quando operador, contexto e
    # AccountCode apontam para donos conflitantes. AccountCode, quando
    # presente, tem precedência e deve estar íntegro.
    context = event.get("DestinationContext") or event.get("Context")
    operator_tenant = extract_tenant(operator, None)
    context_tenant = extract_tenant(None, context)
    if operator_tenant and context_tenant and operator_tenant != context_tenant:
        return None
    account_values = [event[key] for key in ("AccountCode", "Accountcode") if key in event]
    if account_values:
        if (any(not isinstance(value, str) or
                re.fullmatch(r"t[1-9][0-9]*", value) is None
                for value in account_values)
                or len(set(account_values)) != 1):
            return None
        tenant = account_values[0]
        if (operator_tenant and operator_tenant != tenant
                or context_tenant and context_tenant != tenant):
            return None
    else:
        # Compatibilidade apenas com os registros AMI legados sem campo.
        tenant = operator_tenant or context_tenant

    try:
        billable_seconds = max(0, int(event.get("BillableSeconds") or 0))
    except (TypeError, ValueError):
        billable_seconds = 0

    date = _extract_date(event.get("EndTime") or event.get("StartTime"))

    caller = event.get("CallerIDNum", "")
    if not isinstance(caller, str) or len(caller) > 40 or not caller.isprintable():
        caller = ""
    record = {
        "date": date,
        "disposition": disposition,
        "operator": operator,
        "tenant": tenant,
        "billable_seconds": billable_seconds,
        "caller_id_num": caller,
    }
    if identifiers:
        record["cdr_uniqueid"] = identifiers[0]
    return record


def _extract_date(timestamp_str):
    """'2024-01-15 10:30:00' -> '2024-01-15'. Sem valor válido, usa hoje."""
    if timestamp_str:
        try:
            return timestamp_str.split(" ")[0]
        except (AttributeError, IndexError):
            pass
    return time.strftime("%Y-%m-%d")


class CallLogStore:
    def __init__(self, path):
        self.path = Path(path)

    def append(self, record: dict):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def load_all(self):
        if not self.path.exists():
            return []
        records = []
        seen_ids = set()
        # Leitura em fluxo; entradas inválidas jamais derrubam a consulta.
        with self.path.open("r", encoding="utf-8") as history:
            for line in history:
                if len(line) > _MAX_REPORT_LINE:
                    continue
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except (ValueError, TypeError):
                    continue
                if (not isinstance(row, dict)
                        or not isinstance(row.get("date"), str)
                        or re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["date"]) is None
                        or not isinstance(row.get("disposition"), str)
                        or type(row.get("billable_seconds")) is not int
                        or row["billable_seconds"] < 0):
                    continue
                uniqueid = row.get("cdr_uniqueid")
                if uniqueid is not None:
                    if not isinstance(uniqueid, str) or _CDR_ID.fullmatch(uniqueid) is None:
                        continue
                    dedup_key = (row.get("tenant"), uniqueid)
                    if dedup_key in seen_ids:
                        continue
                    seen_ids.add(dedup_key)
                records.append(row)
        return records

    def query(self, start=None, end=None, operator=None, tenant=None):
        records = self.load_all()
        if start:
            records = [r for r in records if r["date"] >= start]
        if end:
            records = [r for r in records if r["date"] <= end]
        if operator:
            records = [r for r in records if r.get("operator") == operator]
        if tenant:
            records = [r for r in records if r.get("tenant") == tenant]
        return records


def aggregate(records: list) -> dict:
    total = len(records)
    answered = [r for r in records if r["disposition"] == "ANSWERED"]
    missed = total - len(answered)
    talk_seconds = sum(r["billable_seconds"] for r in answered)

    return {
        "total_calls": total,
        "answered_calls": len(answered),
        "missed_calls": missed,
        "average_talk_seconds": round(talk_seconds / len(answered), 1) if answered else 0,
        "missed_rate_percent": round(missed / total * 100, 1) if total else 0,
    }


def group_by(records: list, key_field: str) -> dict:
    """Agrupa por 'operator', 'tenant' ou 'date' e agrega cada grupo."""
    groups = {}
    for record in records:
        key = record.get(key_field) or "desconhecido"
        groups.setdefault(key, []).append(record)
    return {key: aggregate(group) for key, group in groups.items()}
