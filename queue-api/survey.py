"""
Pesquisa de satisfação pós-atendimento (backlog #27). O dialplan
(contexto [pesquisa-satisfacao] em extensions.conf) manda a nota
digitada pelo cliente via UserEvent, junto com o canal do atendente
que participou da chamada (${DIALEDPEERNAME}, preenchido
automaticamente pelo Asterisk).

Lógica pura, sem rede - 100% testável. Persistência em JSONL, mesmo
padrão de reports.py (call_log.jsonl) - permite consultar por
atendente/equipe depois.
"""
import json
import re
import time
from pathlib import Path

OPERATOR_RE = re.compile(r"^PJSIP/([a-zA-Z0-9-]+)-[0-9a-fA-F]+$")


def extract_operator_from_channel(channel: str):
    """Mesmo padrão já usado em reports.py - 'PJSIP/t1-recepcao-00000003' -> 't1-recepcao'."""
    if not channel:
        return None
    match = OPERATOR_RE.match(channel)
    return match.group(1) if match else None


def parse_survey_event(event: dict):
    """
    Extrai o resultado de um evento AMI UserEvent/SatisfactionSurvey,
    validando que a nota é um número inteiro de 1 a 5. Retorna None
    se o evento não servir ou a nota for inválida (ex: cliente digitou
    "6" ou "0" por engano, ou não veio nota nenhuma).
    """
    if event.get("Event") != "UserEvent" or event.get("UserEvent") != "SatisfactionSurvey":
        return None

    try:
        score = int(event.get("Nota", ""))
    except (TypeError, ValueError):
        return None

    if score < 1 or score > 5:
        return None

    return {
        "score": score,
        "operator": extract_operator_from_channel(event.get("Operator", "")),
        "caller_id_num": event.get("CallerIDNum", ""),
        "date": time.strftime("%Y-%m-%d"),
    }


class SurveyStore:
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
                continue
        return records

    def query(self, operator=None):
        records = self.load_all()
        if operator:
            records = [r for r in records if r.get("operator") == operator]
        return records


def average_score(records: list):
    """None (não 0) quando não há registros - '0 de satisfação' seria enganoso."""
    if not records:
        return None
    return round(sum(r["score"] for r in records) / len(records), 2)


def score_distribution(records: list) -> dict:
    """Quantas respostas cada nota (1-5) recebeu."""
    distribution = {str(n): 0 for n in range(1, 6)}
    for r in records:
        distribution[str(r["score"])] = distribution.get(str(r["score"]), 0) + 1
    return distribution


def summarize_by_operator(records: list) -> dict:
    """Agrupa por atendente: média e quantidade de respostas de cada um."""
    by_operator = {}
    for r in records:
        key = r.get("operator") or "desconhecido"
        by_operator.setdefault(key, []).append(r)

    return {
        operator: {"average": average_score(group), "count": len(group)}
        for operator, group in by_operator.items()
    }
