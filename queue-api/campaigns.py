"""
Discador automático / campanhas (backlog #25). Reaproveita o mesmo
contexto de dialplan do click-to-call (manual 12: liga pro ramal do
atendente, e quando atende, completa pro número do contato) - aqui só
adiciona uma lista de contatos e o controle de quantas tentativas
foram feitas e com que resultado.

Lógica pura de validação/armazenamento aqui - a chamada AMI de
verdade (Originate) fica isolada no server.py, mesmo padrão do resto
do projeto.
"""
import json
import re
import secrets
import time
from pathlib import Path

NUMBER_RE = re.compile(r"^[0-9]{8,20}$")
MAX_ATTEMPTS = 3

# Mapeia o resultado de DialEnd (manual 11) pro status do contato
DISPOSITION_TO_STATUS = {
    "ANSWER": "atendida",
    "BUSY": "ocupado",
    "NOANSWER": "sem_resposta",
    "CANCEL": "cancelada",
    "CONGESTION": "falha",
}

DIAL_STRING_RE = re.compile(r"PJSIP/(\d+)@gateway-tdm")


def extract_dialed_number(event: dict):
    """
    Extrai o número discado a partir do campo 'Dialstring' de um
    evento DialEnd (formato tipo 'PJSIP/5511999998888@gateway-tdm').
    Sem isso, não dá pra saber qual contato da campanha aquele
    resultado pertence.
    """
    dialstring = event.get("Dialstring", "")
    match = DIAL_STRING_RE.search(dialstring)
    if match:
        return match.group(1)
    return event.get("DestExten") or None


def sanitize_phone_number(raw: str):
    """Mesma sanitização já usada no click-to-call (manual 12): só dígitos."""
    if not raw or not isinstance(raw, str):
        return None
    digits = re.sub(r"[^0-9]", "", raw.strip())
    return digits if NUMBER_RE.match(digits) else None


def load_campaigns(path) -> list:
    path = Path(path)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_campaigns(path, campaigns: list):
    Path(path).write_text(json.dumps(campaigns, indent=2, ensure_ascii=False), encoding="utf-8")


def find_campaign(campaigns: list, campaign_id: str):
    return next((c for c in campaigns if c["id"] == campaign_id), None)


def validate_campaign_input(data: dict):
    """Retorna (ok, error_message, cleaned_data)."""
    name = (data.get("name") or "").strip()
    if not name:
        return False, "nome da campanha obrigatório", None

    agent_extension = (data.get("agent_extension") or "").strip()
    if not agent_extension:
        return False, "ramal do atendente obrigatório", None

    raw_contacts = data.get("contacts") or []
    if not raw_contacts:
        return False, "lista de contatos não pode ser vazia", None

    contacts = []
    for raw_number in raw_contacts:
        number = sanitize_phone_number(raw_number)
        if number:
            contacts.append({
                "number": number,
                "status": "pendente",
                "attempts": 0,
                "last_attempt_at": None,
            })

    if not contacts:
        return False, "nenhum número válido na lista de contatos", None

    return True, None, {
        "id": secrets.token_hex(6),
        "name": name,
        "agent_extension": agent_extension,
        "created_at": time.time(),
        "contacts": contacts,
    }


def create_campaign(path, data: dict):
    ok, error, campaign = validate_campaign_input(data)
    if not ok:
        return False, error, None

    campaigns = load_campaigns(path)
    campaigns.append(campaign)
    save_campaigns(path, campaigns)
    return True, None, campaign


def next_pending_contact(campaign: dict):
    """Primeiro contato ainda não discado (ou pra rediscar, se voltou a 'pendente')."""
    for contact in campaign["contacts"]:
        if contact["status"] == "pendente":
            return contact
    return None


def mark_contact_calling(path, campaign_id: str, number: str):
    campaigns = load_campaigns(path)
    campaign = find_campaign(campaigns, campaign_id)
    if not campaign:
        return False, f"campanha '{campaign_id}' não encontrada"

    contact = next((c for c in campaign["contacts"] if c["number"] == number), None)
    if not contact:
        return False, f"contato '{number}' não encontrado na campanha"

    contact["status"] = "discando"
    contact["attempts"] += 1
    contact["last_attempt_at"] = time.time()
    save_campaigns(path, campaigns)
    return True, None


def mark_contact_result(path, campaign_id: str, number: str, disposition: str):
    """
    Aplica o resultado de uma tentativa. Se não atendeu e ainda não
    esgotou as tentativas, volta pra 'pendente' (será tentado de novo);
    senão vira 'esgotado'.
    """
    campaigns = load_campaigns(path)
    campaign = find_campaign(campaigns, campaign_id)
    if not campaign:
        return False, f"campanha '{campaign_id}' não encontrada"

    contact = next((c for c in campaign["contacts"] if c["number"] == number), None)
    if not contact:
        return False, f"contato '{number}' não encontrado na campanha"

    status = DISPOSITION_TO_STATUS.get(disposition, "falha")
    if status != "atendida" and contact["attempts"] < MAX_ATTEMPTS:
        status = "pendente"  # tenta de novo mais tarde
    elif status != "atendida":
        status = "esgotado"

    contact["status"] = status
    save_campaigns(path, campaigns)
    return True, None


def campaign_summary(campaign: dict) -> dict:
    """Contagem de contatos por status - visão rápida do progresso."""
    summary = {}
    for contact in campaign["contacts"]:
        summary[contact["status"]] = summary.get(contact["status"], 0) + 1
    summary["total"] = len(campaign["contacts"])
    return summary
