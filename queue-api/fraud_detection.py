"""
Detecção de fraude (backlog #32): volume anormal de chamadas de
saída por ramal, e limite de gasto diário por ramal. Reaproveita a
extração de atendente já usada nos relatórios (reports.py) e a mesma
lista de bloqueio (AstDB família "blocklist") já consultada pelo
dialplan (manual 20) - bloquear um destino suspeito aqui tem efeito
imediato, sem precisar de nenhum mecanismo novo no Asterisk.

Lógica pura, sem rede - 100% testável.
"""
import math
import time

from reports import extract_operator
from monitoring_access import extension_tenant


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
        if (not isinstance(extension, str) or not 1 <= len(extension) <= 96
                or not isinstance(destination, str) or not 1 <= len(destination) <= 128
                or not extension.isprintable() or not destination.isprintable()):
            return
        now = self._clock()
        # Retenção deslizante de 24 h; poda somente quando o primeiro
        # evento estiver vencido, evitando recomputar toda a lista a
        # cada chamada (importante em ramais de alto tráfego).
        horizon = now - 86400
        calls = self._calls.setdefault(extension, [])
        if calls and calls[0][0] < horizon:
            expired = 0
            while expired < len(calls) and calls[expired][0] < horizon:
                expired += 1
            del calls[:expired]
        calls.append((now, destination))
        if len(calls) > 10000:
            del calls[:-10000]

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
        if type(max_size) is not int or not 1 <= max_size <= 10000:
            raise ValueError("limite de alertas inválido")
        self._entries = []
        self._max_size = max_size

    def append(self, alert_type: str, extension: str, detail: str):
        entry = {
            "type": alert_type,
            "extension": extension,
            "tenant": extension_tenant(extension),
            "detail": detail,
            "timestamp": time.time(),
        }
        self._entries.append(entry)
        if len(self._entries) > self._max_size:
            self._entries.pop(0)

    def list(self, limit=20):
        if type(limit) is not int or limit <= 0:
            return []
        return [dict(entry) for entry in reversed(self._entries)][:min(limit, self._max_size)]


def is_external_call(event: dict) -> bool:
    """
    Um DialBegin conta como chamada externa se o canal de destino é
    um dos troncos (gateway-tdm ou gateway-tdm-2) - internas entre
    ramais não custam nada e não fazem sentido pra essa análise.
    """
    if not isinstance(event, dict):
        return False
    dest_channel = event.get("DestChannel", "")
    return isinstance(dest_channel, str) and "@gateway-tdm" in dest_channel and ("@gateway-tdm-" in dest_channel or dest_channel.endswith("@gateway-tdm"))


def compute_daily_cost(records: list, cost_per_minute: float) -> float:
    """
    Soma o tempo de conversa (billable_seconds) de uma lista de
    registros de chamada (ver reports.py) e converte pra custo
    estimado, dado um valor por minuto.
    """
    if (not isinstance(records, (list, tuple))
            or type(cost_per_minute) not in (int, float)
            or not math.isfinite(cost_per_minute) or cost_per_minute < 0):
        return 0.0
    seconds = 0
    for record in records:
        if not isinstance(record, dict) or record.get("disposition") != "ANSWERED":
            continue
        duration = record.get("billable_seconds")
        if (type(duration) in (int, float) and math.isfinite(duration)
                and 0 <= duration <= 30 * 86400):
            seconds += duration
    return round((seconds / 60) * cost_per_minute, 2)


def is_over_spending_limit(records: list, cost_per_minute: float, daily_limit: float) -> bool:
    """daily_limit <= 0 desabilita a checagem (opt-in, como o resto do projeto)."""
    if (type(daily_limit) not in (int, float)
            or not math.isfinite(daily_limit) or daily_limit <= 0):
        return False
    return compute_daily_cost(records, cost_per_minute) > daily_limit
