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
        if event.get("Event") != "Cdr":
            return

        self._reset_if_new_day()

        disposition = event.get("Disposition")
        if not disposition:
            return

        self.total_calls += 1

        if disposition == "ANSWERED":
            self.answered_calls += 1
            try:
                self.total_talk_seconds += int(event.get("BillableSeconds") or 0)
            except (TypeError, ValueError):
                pass
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
