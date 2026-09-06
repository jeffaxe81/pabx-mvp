"""
Detecção de fraude (backlog #32): volume anormal de chamadas de
saída por ramal, e limite de gasto diário por ramal. Reaproveita a
extração de atendente já usada nos relatórios (reports.py) e a mesma
lista de bloqueio (AstDB família "blocklist") já consultada pelo
dialplan (manual 20) - bloquear um destino suspeito aqui tem efeito
imediato, sem precisar de nenhum mecanismo novo no Asterisk.

Lógica pura, sem rede - 100% testável.
"""
import time

from reports import extract_operator


class CallRateTracker:
    """
    Detecta volume anormal: mais de N chamadas de saída pelo mesmo
    ramal numa janela de tempo curta é um padrão clássico de fraude
    (PABX comprometido discando em massa).
    """

    def __init__(self, clock=time.time):
        self._clock = clock
        self._calls = {}  # extension -> lista de timestamps

    def track_call(self, extension: str, destination: str):
        if not extension:
            return
        self._calls.setdefault(extension, []).append((self._clock(), destination))

    def is_abnormal(self, extension: str, window_seconds: int = 60, threshold: int = 10) -> bool:
        calls = self._calls.get(extension, [])
        cutoff = self._clock() - window_seconds
        recent = [c for c in calls if c[0] >= cutoff]
        return len(recent) > threshold

    def recent_destinations(self, extension: str, window_seconds: int = 60):
        calls = self._calls.get(extension, [])
        cutoff = self._clock() - window_seconds
        return [dest for ts, dest in calls if ts >= cutoff]


class FraudAlertsLog:
    """Histórico de alertas de fraude, mesmo padrão do MissedCallsLog (queue_state.py)."""

    def __init__(self, max_size=100):
        self._entries = []
        self._max_size = max_size

    def append(self, alert_type: str, extension: str, detail: str):
        entry = {
            "type": alert_type,
            "extension": extension,
            "detail": detail,
            "timestamp": time.time(),
        }
        self._entries.append(entry)
        if len(self._entries) > self._max_size:
            self._entries.pop(0)

    def list(self, limit=20):
        return list(reversed(self._entries))[:limit]


def is_external_call(event: dict) -> bool:
    """
    Um DialBegin conta como chamada externa se o canal de destino é
    um dos troncos (gateway-tdm ou gateway-tdm-2) - internas entre
    ramais não custam nada e não fazem sentido pra essa análise.
    """
    dest_channel = event.get("DestChannel", "")
    return "gateway-tdm" in dest_channel


def compute_daily_cost(records: list, cost_per_minute: float) -> float:
    """
    Soma o tempo de conversa (billable_seconds) de uma lista de
    registros de chamada (ver reports.py) e converte pra custo
    estimado, dado um valor por minuto.
    """
    total_seconds = sum(r.get("billable_seconds", 0) for r in records if r.get("disposition") == "ANSWERED")
    return round((total_seconds / 60) * cost_per_minute, 2)


def is_over_spending_limit(records: list, cost_per_minute: float, daily_limit: float) -> bool:
    """daily_limit <= 0 desabilita a checagem (opt-in, como o resto do projeto)."""
    if daily_limit <= 0:
        return False
    return compute_daily_cost(records, cost_per_minute) > daily_limit
