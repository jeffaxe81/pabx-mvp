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

OPERATOR_RE = re.compile(r"^PJSIP/([a-zA-Z0-9-]+)-[0-9a-fA-F]+$")
TENANT_RE = re.compile(r"^(t\d+)-")


def extract_operator(channel: str):
    """'PJSIP/t1-recepcao-00000003' -> 't1-recepcao'. None se não bater o padrão."""
    if not channel:
        return None
    match = OPERATOR_RE.match(channel)
    return match.group(1) if match else None


def extract_tenant(operator: str, context: str):
    """Tenta primeiro pelo prefixo do operador, depois pelo contexto."""
    for candidate in (operator, context):
        if candidate:
            match = TENANT_RE.match(candidate)
            if match:
                return match.group(1)
    return None


def parse_cdr_for_report(event: dict):
    """
    Transforma um evento AMI 'Cdr' num registro de relatório, ou
    retorna None se o evento não servir (não é Cdr, ou sem disposition).
    """
    if event.get("Event") != "Cdr":
        return None

    disposition = event.get("Disposition")
    if not disposition:
        return None

    channel = event.get("DestinationChannel") or event.get("Channel") or ""
    operator = extract_operator(channel)
    tenant = extract_tenant(operator, event.get("DestinationContext") or event.get("Context"))

    try:
        billable_seconds = int(event.get("BillableSeconds") or 0)
    except (TypeError, ValueError):
        billable_seconds = 0

    date = _extract_date(event.get("EndTime") or event.get("StartTime"))

    return {
        "date": date,
        "disposition": disposition,
        "operator": operator,
        "tenant": tenant,
        "billable_seconds": billable_seconds,
        "caller_id_num": event.get("CallerIDNum", ""),
    }


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
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # linha corrompida não derruba o resto do relatório
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
