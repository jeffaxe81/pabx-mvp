"""
Mantém em memória a lista de chamadas esperando em cada fila,
atualizada a partir dos eventos AMI recebidos (QueueCallerJoin /
QueueCallerLeave). Lógica pura - não depende de rede, 100% testável.
"""
import time


class QueueStateTracker:
    def __init__(self):
        # channel -> {queue, caller_id_num, caller_id_name, joined_at}
        self._waiting = {}

    def apply_event(self, event: dict):
        event_name = event.get("Event")

        if event_name == "QueueCallerJoin":
            channel = event.get("Channel")
            if not channel:
                return
            self._waiting[channel] = {
                "channel": channel,
                "queue": event.get("Queue"),
                "caller_id_num": event.get("CallerIDNum", ""),
                "caller_id_name": event.get("CallerIDName", ""),
                "joined_at": time.time(),
            }

        elif event_name == "QueueCallerLeave":
            channel = event.get("Channel")
            self._waiting.pop(channel, None)

        elif event_name == "Hangup":
            # segurança extra: se o canal caiu por qualquer motivo,
            # não deve continuar aparecendo como "esperando"
            channel = event.get("Channel")
            self._waiting.pop(channel, None)

    def waiting_list(self, queue_name: str = None):
        """
        Retorna a lista de chamadas esperando, ordenada da mais antiga
        pra mais nova (quem espera há mais tempo aparece primeiro -
        mas a telefonista pode escolher qualquer uma, não só a primeira).
        """
        items = list(self._waiting.values())
        if queue_name:
            items = [i for i in items if i["queue"] == queue_name]

        items.sort(key=lambda i: i["joined_at"])

        now = time.time()
        return [
            {
                "channel": i["channel"],
                "queue": i["queue"],
                "caller_id_num": i["caller_id_num"],
                "caller_id_name": i["caller_id_name"],
                "waiting_seconds": int(now - i["joined_at"]),
            }
            for i in items
        ]

    def remove(self, channel: str):
        """Remoção manual (ex: logo após um pickup bem-sucedido)."""
        self._waiting.pop(channel, None)
