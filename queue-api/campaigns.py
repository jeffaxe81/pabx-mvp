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
import math
import re
import secrets
import time
from pathlib import Path

from outbound_safety import atomic_write_json

NUMBER_RE = re.compile(r"^[0-9]{8,20}$")
_CAMPAIGN_ID = re.compile(r"[0-9a-f]{12}\Z")
_AGENT = re.compile(r"(t[1-9][0-9]*)-[a-z0-9][a-z0-9-]{0,78}\Z")
_PHONE_FORMAT = re.compile(r"\+?[0-9 ()-]+\Z")
_ATTEMPT_ID = re.compile(r"[0-9a-f]{32}\Z")
_ALLOWED_STATES = frozenset({
    "pendente", "discando", "atendida", "ocupado", "sem_resposta",
    "cancelada", "falha", "esgotado", "revisao_manual",
})
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
    raw = raw.strip()
    if len(raw) > 48 or not raw.isascii() or _PHONE_FORMAT.fullmatch(raw) is None:
        return None
    digits = re.sub(r"[^0-9]", "", raw)
    return digits if NUMBER_RE.fullmatch(digits) else None


def _reject_duplicate_keys(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("catalogo de campanhas com campo JSON duplicado")
        result[name] = value
    return result


def _reject_nonfinite(value):
    raise ValueError("catalogo de campanhas com valor JSON nao finito")


def validate_campaign_catalog(campaigns):
    """Refuse ambiguous pending claims without echoing caller data.

    Legacy campaigns without tenant remain readable but cannot be dialed
    through the authenticated tenant-scoped API.
    """
    if not isinstance(campaigns, list) or len(campaigns) > 10000:
        raise ValueError("catalogo de campanhas invalido ou excessivo")
    seen_ids = set()
    for campaign in campaigns:
        if not isinstance(campaign, dict):
            raise ValueError("registro de campanha invalido")
        cid = campaign.get("id")
        if not isinstance(cid, str) or _CAMPAIGN_ID.fullmatch(cid) is None or cid in seen_ids:
            raise ValueError("id de campanha invalido ou duplicado")
        seen_ids.add(cid)
        agent = campaign.get("agent_extension")
        owner = _AGENT.fullmatch(agent) if isinstance(agent, str) else None
        tenant = campaign.get("tenant")
        if owner is None or tenant is not None and owner.group(1) != tenant:
            raise ValueError("ramal de campanha fora do tenant")
        name = campaign.get("name")
        if not isinstance(name, str) or not 1 <= len(name) <= 100 or not name.isprintable():
            raise ValueError("nome de campanha invalido")
        contacts = campaign.get("contacts")
        if not isinstance(contacts, list) or not 1 <= len(contacts) <= 1000:
            raise ValueError("lista de contatos de campanha invalida")
        seen_numbers = set()
        for contact in contacts:
            if not isinstance(contact, dict):
                raise ValueError("contato de campanha invalido")
            number = contact.get("number")
            if not isinstance(number, str) or NUMBER_RE.fullmatch(number) is None or number in seen_numbers:
                raise ValueError("numero de campanha invalido ou duplicado")
            seen_numbers.add(number)
            status, attempts = contact.get("status"), contact.get("attempts")
            if (not isinstance(status, str) or status not in _ALLOWED_STATES
                    or type(attempts) is not int
                    or not 0 <= attempts <= MAX_ATTEMPTS
                    or status == "pendente" and attempts >= MAX_ATTEMPTS):
                raise ValueError("estado de campanha inconsistente")
            if status == "discando":
                attempt_id, channel_id = contact.get("attempt_id"), contact.get("channel_id")
                started = contact.get("last_attempt_at")
                if (attempts < 1 or not isinstance(attempt_id, str)
                        or _ATTEMPT_ID.fullmatch(attempt_id) is None
                        or channel_id != "axe-" + attempt_id
                        or type(started) not in (int, float)
                        or not math.isfinite(started) or started < 0):
                    raise ValueError("tentativa de campanha nao correlacionavel")
    return True


def load_campaigns(path) -> list:
    path = Path(path)
    if path.is_symlink():
        raise ValueError("catalogo de campanhas em link simbolico")
    if not path.exists():
        return []
    if not path.is_file():
        raise ValueError("catalogo de campanhas nao regular")
    data = json.loads(path.read_text(encoding="utf-8"),
                      object_pairs_hook=_reject_duplicate_keys,
                      parse_constant=_reject_nonfinite)
    validate_campaign_catalog(data)
    return data


def save_campaigns(path, campaigns: list):
    atomic_write_json(path, campaigns)


def find_campaign(campaigns: list, campaign_id: str):
    if (not isinstance(campaign_id, str) or not isinstance(campaigns, list)
            or sum(isinstance(c, dict) and c.get("id") == campaign_id for c in campaigns) != 1):
        return None
    return next(c for c in campaigns if c["id"] == campaign_id)


def validate_campaign_input(data: dict):
    """Retorna (ok, error_message, cleaned_data)."""
    if not isinstance(data, dict):
        return False, "campanha deve ser objeto JSON", None
    if not isinstance(data.get("name", ""), str) or not isinstance(data.get("agent_extension", ""), str):
        return False, "nome ou ramal inválido", None
    name = (data.get("name") or "").strip()
    if not name:
        return False, "nome da campanha obrigatório", None
    if len(name) > 100 or not name.isprintable():
        return False, "nome de campanha invalido", None

    agent_extension = (data.get("agent_extension") or "").strip()
    if not agent_extension:
        return False, "ramal do atendente obrigatório", None
    if _AGENT.fullmatch(agent_extension) is None:
        return False, "ramal do atendente invalido", None

    raw_contacts = data.get("contacts") or []
    if not isinstance(raw_contacts, list) or len(raw_contacts) > 1000:
        return False, "lista de contatos inválida ou excessiva", None
    if not raw_contacts:
        return False, "lista de contatos não pode ser vazia", None

    contacts = []
    numbers_seen = set()
    for raw_number in raw_contacts:
        number = sanitize_phone_number(raw_number)
        if number and number not in numbers_seen:
            numbers_seen.add(number)
            contacts.append({
                "number": number,
                "status": "pendente",
                "attempts": 0,
                "last_attempt_at": None,
            })

    if not contacts:
        return False, "nenhum número válido na lista de contatos", None

    result = {
        "id": secrets.token_hex(6),
        "name": name,
        "agent_extension": agent_extension,
        "created_at": time.time(),
        "contacts": contacts,
    }
    # A identidade só é inserida pelo serviço HTTP autenticado.
    if data.get("tenant") is not None:
        from monitoring_access import extension_tenant
        tenant = data["tenant"]
        if not isinstance(tenant, str) or extension_tenant(agent_extension) != tenant:
            return False, "ramal ou tenant nao autorizado", None
        result["tenant"] = tenant
    return True, None, result


def create_campaign(path, data: dict):
    ok, error, campaign = validate_campaign_input(data)
    if not ok:
        return False, error, None

    campaigns = load_campaigns(path)
    existing_ids = {item["id"] for item in campaigns}
    for _ in range(20):
        if campaign["id"] not in existing_ids:
            break
        campaign["id"] = secrets.token_hex(6)
    else:
        return False, "nao foi possivel gerar ID unico", None
    campaigns.append(campaign)
    validate_campaign_catalog(campaigns)
    save_campaigns(path, campaigns)
    return True, None, campaign


def next_pending_contact(campaign: dict):
    """Primeiro contato ainda não discado (ou pra rediscar, se voltou a 'pendente')."""
    for contact in campaign["contacts"]:
        if (contact.get("status") == "pendente"
                and type(contact.get("attempts", 0)) is int
                and contact.get("attempts", 0) < MAX_ATTEMPTS):
            return contact
    return None


def mark_contact_calling(path, campaign_id: str, number: str, attempt_id=None):
    campaigns = load_campaigns(path)
    campaign = find_campaign(campaigns, campaign_id)
    if not campaign:
        return False, f"campanha '{campaign_id}' não encontrada"

    contact = next((c for c in campaign["contacts"] if c["number"] == number), None)
    if not contact:
        return False, f"contato '{number}' não encontrado na campanha"

    if contact.get("status") != "pendente":
        return False, "contato ja reservado"
    if type(contact.get("attempts")) is not int or not 0 <= contact["attempts"] < MAX_ATTEMPTS:
        return False, "limite de tentativas do contato atingido"
    attempt_id = attempt_id or secrets.token_hex(16)
    if not isinstance(attempt_id, str) or not re.fullmatch(r"[a-f0-9]{32}", attempt_id):
        return False, "id de tentativa invalido"
    contact["status"] = "discando"
    contact["attempts"] += 1
    contact["last_attempt_at"] = time.time()
    contact["attempt_id"] = attempt_id
    contact["channel_id"] = "axe-" + attempt_id
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

    contact = next((c for c in campaign["contacts"]
                    if c["number"] == number and c["status"] == "discando"), None)
    if not contact:
        return False, "contato nao esta discando"

    if contact["status"] != "discando":
        return False, "contato nao esta discando"

    if not isinstance(disposition, str) or disposition not in DISPOSITION_TO_STATUS:
        return False, "resultado AMI desconhecido"
    if type(contact.get("attempts")) is not int or not 1 <= contact["attempts"] <= MAX_ATTEMPTS:
        return False, "contador de tentativas invalido"
    status = DISPOSITION_TO_STATUS[disposition]
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
