"""
Métricas do dia (volume de chamadas, taxa de perdidas, tempo médio de
atendimento), alimentadas pelos eventos CDR do Asterisk (habilitados
em asterisk/cdr_manager.conf - um evento "Cdr" por chamada finalizada,
já com status e duração calculados pelo próprio Asterisk).

Lógica pura, sem rede - 100% testável. O relógio é injetável (clock)
justamente pra dar pra testar a virada do dia sem precisar esperar a
meia-noite de verdade.
"""
import time


def _day_key(timestamp: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(timestamp))


MAX_BILLABLE_SECONDS = 30 * 24 * 3600


def _billable_seconds(value):
    """Aceitar somente duração integral em segundos, sem truncamento."""
    if type(value) is int:
        n = value
    elif isinstance(value, str) and value.isascii() and value.isdecimal() and len(value) <= 10:
        n = int(value)
    else:
        return None
    return n if 0 <= n <= MAX_BILLABLE_SECONDS else None


class DailyMetrics:
    def __init__(self, clock=time.time):
        self._clock = clock
        self._day = None
        self._reset_if_new_day()

    def _reset_if_new_day(self):
        today = _day_key(self._clock())
        if today != self._day:
            self._day = today
            self.total_calls = 0
            self.answered_calls = 0
            self.missed_calls = 0
            self.total_talk_seconds = 0

    def apply_cdr_event(self, event: dict):
        if not isinstance(event, dict) or event.get("Event") != "Cdr":
            return

        self._reset_if_new_day()

        disposition = event.get("Disposition")
        if (not isinstance(disposition, str) or not disposition
                or len(disposition) > 32 or not disposition.isprintable()):
            return

        self.total_calls += 1

        if disposition == "ANSWERED":
            self.answered_calls += 1
            duration = _billable_seconds(event.get("BillableSeconds"))
            if duration is not None:
                self.total_talk_seconds += duration
        else:
            self.missed_calls += 1

    def snapshot(self) -> dict:
        self._reset_if_new_day()

        avg_talk_seconds = (
            round(self.total_talk_seconds / self.answered_calls, 1)
            if self.answered_calls else 0
        )
        missed_rate_percent = (
            round(self.missed_calls / self.total_calls * 100, 1)
            if self.total_calls else 0
        )

        return {
            "date": self._day,
            "total_calls": self.total_calls,
            "answered_calls": self.answered_calls,
            "missed_calls": self.missed_calls,
            "average_talk_seconds": avg_talk_seconds,
            "missed_rate_percent": missed_rate_percent,
        }


# A métrica legada agregada continua disponível apenas em memória.
# Novas APIs multiempresa usam exclusivamente AccountCode do CDR,
# atribuído pelo dialplan e proveniente dos eventos AMI do Asterisk.
import re

_ACCOUNT_TENANT = re.compile(r"^t[1-9][0-9]*$")
MAX_DAILY_TENANTS = 256


def tenant_from_cdr(event):
    """Aceita exclusivamente um accountcode completo e inequívoco."""
    if not isinstance(event, dict) or event.get("Event") != "Cdr":
        return None
    values = [event[key] for key in ("AccountCode", "Accountcode")
              if key in event]
    if (not values or any(not isinstance(v, str) or
                          not _ACCOUNT_TENANT.fullmatch(v) for v in values)
            or len(set(values)) != 1):
        return None
    return values[0]


class TenantDailyMetrics:
    """Métricas isoladas, nunca atribui CDR sem AccountCode confiável."""

    def __init__(self, clock=time.time):
        self._clock = clock
        self._day = _day_key(clock())
        self._by_tenant = {}

    def _roll_day(self):
        today = _day_key(self._clock())
        if today != self._day:
            self._day = today
            self._by_tenant.clear()

    def apply_cdr_event(self, event):
        self._roll_day()
        tenant = tenant_from_cdr(event)
        if tenant is None or not event.get("Disposition"):
            return
        if tenant not in self._by_tenant:
            if len(self._by_tenant) >= MAX_DAILY_TENANTS:
                return
            self._by_tenant[tenant] = DailyMetrics(clock=self._clock)
        self._by_tenant[tenant].apply_cdr_event(event)

    def snapshot(self, tenant):
        self._roll_day()
        if not isinstance(tenant, str) or not _ACCOUNT_TENANT.fullmatch(tenant):
            return None
        if tenant in self._by_tenant:
            return self._by_tenant[tenant].snapshot()
        return {
            "date": self._day, "total_calls": 0, "answered_calls": 0,
            "missed_calls": 0, "average_talk_seconds": 0,
            "missed_rate_percent": 0,
        }
