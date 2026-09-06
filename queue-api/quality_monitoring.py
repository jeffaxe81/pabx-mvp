"""
Monitoramento de qualidade de chamada (backlog #34): parseia o evento
customizado "QualityStats" (emitido pelo dialplan via UserEvent, ver
extensions.conf contexto [qualidade-chamada]) e verifica se os
valores de jitter/perda de pacotes/RTT passam de um limiar aceitável.

Lógica pura, sem rede - 100% testável. Os valores de RTCP vêm do
Asterisk como string, e podem vir vazios se a chamada foi curta demais
ou o codec/transporte não gerou dado - tratado com cuidado abaixo.
"""
import time


def _parse_float_or_none(value):
    """Converte string do Asterisk pra float, tratando vazio/inválido como None."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_quality_event(event: dict):
    """
    Extrai as métricas de um evento AMI UserEvent/QualityStats, ou
    retorna None se o evento não for esse.
    """
    if event.get("Event") != "UserEvent" or event.get("UserEvent") != "QualityStats":
        return None

    return {
        "channel": event.get("Channel", ""),
        "jitter_ms": _parse_float_or_none(event.get("Jitter")),
        "packet_loss_percent": _parse_float_or_none(event.get("PacketLoss")),
        "rtt_ms": _parse_float_or_none(event.get("RTT")),
    }


def is_poor_quality(quality: dict, jitter_threshold_ms: float = 30.0, packet_loss_threshold_percent: float = 3.0) -> bool:
    """
    True se qualquer métrica disponível passar do limiar. Métricas
    ausentes (None) são ignoradas, não contam como "ruim" nem "boa" -
    dado que não veio não pode virar alarme falso.
    """
    jitter = quality.get("jitter_ms")
    packet_loss = quality.get("packet_loss_percent")

    if jitter is not None and jitter > jitter_threshold_ms:
        return True
    if packet_loss is not None and packet_loss > packet_loss_threshold_percent:
        return True
    return False


class QualityLog:
    """Histórico de relatórios de qualidade, mesmo padrão do FraudAlertsLog."""

    def __init__(self, max_size=100):
        self._entries = []
        self._max_size = max_size

    def append(self, quality: dict, poor: bool):
        entry = {**quality, "poor": poor, "timestamp": time.time()}
        self._entries.append(entry)
        if len(self._entries) > self._max_size:
            self._entries.pop(0)

    def list(self, limit=20, only_poor=False):
        entries = list(reversed(self._entries))
        if only_poor:
            entries = [e for e in entries if e["poor"]]
        return entries[:limit]
