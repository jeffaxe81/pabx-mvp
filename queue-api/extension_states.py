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
MAX_TRACKED_EXTENSIONS = 10000

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
        self._states = {}  # (context, exten) -> {status_code, status_text, context}

    def apply_event(self, event: dict):
        if not isinstance(event, dict) or event.get("Event") != "ExtensionStatus":
            return

        exten = event.get("Exten")
        context = event.get("Context", "")
        status_code = event.get("Status", "-1")
        # IDs são usados como chaves e exibidos na supervisão. Nunca
        # deixar estruturas AMI ou caracteres de controle contaminar
        # o mapa (inclusive quando o mesmo ramal existe em duas empresas).
        if (not isinstance(exten, str) or not 0 < len(exten) <= 64
                or not exten.isprintable() or any(ch.isspace() for ch in exten)
                or not isinstance(context, str) or len(context) > 96
                or not context.isprintable()
                or not isinstance(status_code, str) or len(status_code) > 12
                or not status_code.isprintable()):
            return
        key = (context, exten)
        if key not in self._states and len(self._states) >= MAX_TRACKED_EXTENSIONS:
            return
        self._states[key] = {
            "exten": exten,
            "context": context,
            "status_code": status_code,
            "status_label": STATUS_LABELS.get(status_code, "desconhecido"),
        }

    def snapshot(self):
        # Cópias impedem que o painel externo altere o cache AMI interno.
        return sorted((dict(value) for value in self._states.values()),
                      key=lambda s: (s["exten"], s["context"]))
