"""
Estado de cada ramal monitorado (livre/tocando/ocupado/indisponível),
alimentado pelo evento AMI "ExtensionStatus" - o mesmo mecanismo de
hint já usado pelo BLF da interface web (manual 06), só que aqui do
lado do servidor, pra alimentar um painel consolidado (manual 17) em
vez de uma assinatura SIP por navegador.

Lógica pura, sem rede - 100% testável.
"""

# Códigos de status do Asterisk (AMI ExtensionStatus / app_queue.h).
# Nem todo código aparece na prática, mas mapeamos os mais comuns.
STATUS_LABELS = {
    "-1": "desconhecido",
    "0": "livre",
    "1": "em uso",
    "2": "ocupado",
    "4": "indisponível",
    "8": "tocando",
    "16": "em espera",
}


class ExtensionStateTracker:
    def __init__(self):
        self._states = {}  # exten -> {status_code, status_text, context}

    def apply_event(self, event: dict):
        if event.get("Event") != "ExtensionStatus":
            return

        exten = event.get("Exten")
        if not exten:
            return

        status_code = event.get("Status", "-1")
        self._states[exten] = {
            "exten": exten,
            "context": event.get("Context", ""),
            "status_code": status_code,
            "status_label": STATUS_LABELS.get(status_code, "desconhecido"),
        }

    def snapshot(self):
        return sorted(self._states.values(), key=lambda s: s["exten"])
