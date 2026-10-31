"""
Monitoramento de qualidade de chamada (backlog #34): parseia o evento
customizado "QualityStats" (emitido pelo dialplan via UserEvent, ver
extensions.conf contexto [qualidade-chamada]) e verifica se os
valores de jitter/perda de pacotes/RTT passam de um limiar aceitável.

Lógica pura, sem rede - 100% testável. Os valores de RTCP vêm do
Asterisk como string, e podem vir vazios se a chamada foi curta demais
ou o codec/transporte não gerou dado - tratado com cuidado abaixo.
"""
import math
import re
import time


def _parse_float_or_none(value):
    """Converte string do Asterisk pra float, tratando vazio/inválido como None."""
    if (type(value) not in (str, int, float)
            or isinstance(value, str) and (not value or len(value) > 48)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def _parse_loss_percent(value):
    result = _parse_float_or_none(value)
    return result if result is not None and result <= 100 else None


def parse_quality_event(event: dict):
    """
    Extrai as métricas de um evento AMI UserEvent/QualityStats, ou
    retorna None se o evento não for esse.
    """
    if (not isinstance(event, dict) or event.get("Event") != "UserEvent"
            or event.get("UserEvent") != "QualityStats"):
        return None

    channel = event.get("Channel")
    if (not isinstance(channel, str) or not 0 < len(channel) <= 160
            or not channel.isprintable() or any(ch.isspace() for ch in channel)):
        return None
    return {
        "channel": channel,
        "jitter_ms": _parse_float_or_none(event.get("Jitter")),
        "packet_loss_percent": _parse_loss_percent(event.get("PacketLoss")),
        "rtt_ms": _parse_float_or_none(event.get("RTT")),
    }


def is_poor_quality(quality: dict, jitter_threshold_ms: float = 30.0,
                    packet_loss_threshold_percent: float = 3.0,
                    rtt_threshold_ms: float = 300.0) -> bool:
    """
    True se qualquer métrica disponível passar do limiar. Métricas
    ausentes (None) são ignoradas, não contam como "ruim" nem "boa" -
    dado que não veio não pode virar alarme falso.
    """
    if not isinstance(quality, dict):
        return False
    if (type(jitter_threshold_ms) not in (int, float)
            or not math.isfinite(jitter_threshold_ms) or jitter_threshold_ms < 0
            or type(packet_loss_threshold_percent) not in (int, float)
            or not math.isfinite(packet_loss_threshold_percent)
            or not 0 <= packet_loss_threshold_percent <= 100
            or type(rtt_threshold_ms) not in (int, float)
            or not math.isfinite(rtt_threshold_ms) or rtt_threshold_ms < 0):
        return False
    jitter = quality.get("jitter_ms")
    packet_loss = quality.get("packet_loss_percent")
    rtt = quality.get("rtt_ms")

    if (type(jitter) in (int, float) and math.isfinite(jitter)
            and jitter >= 0 and jitter > jitter_threshold_ms):
        return True
    if (type(packet_loss) in (int, float) and math.isfinite(packet_loss)
            and 0 <= packet_loss <= 100 and packet_loss > packet_loss_threshold_percent):
        return True
    if (type(rtt) in (int, float) and math.isfinite(rtt)
            and rtt >= 0 and rtt > rtt_threshold_ms):
        return True
    return False


_QUALITY_TENANT = re.compile(r"t[1-9][0-9]*\\Z")

class QualityLog:
    """Histórico de relatórios de qualidade, mesmo padrão do FraudAlertsLog."""

    def __init__(self, max_size=100):
        if type(max_size) is not int or not 1 <= max_size <= 10000:
            raise ValueError("limite de qualidade invalido")
        self._entries = []
        self._max_size = max_size

    def append(self, quality: dict, poor: bool):
        if not isinstance(quality, dict) or type(poor) is not bool:
            return False
        channel = quality.get("channel")
        if (not isinstance(channel, str) or not 0 < len(channel) <= 160
                or not channel.isprintable()):
            return False
        entry = {"channel": channel}
        for field in ("jitter_ms", "rtt_ms", "packet_loss_percent"):
            if field in quality:
                entry[field] = (_parse_loss_percent(quality[field])
                                if field == "packet_loss_percent"
                                else _parse_float_or_none(quality[field]))
        tenant = quality.get("tenant")
        if isinstance(tenant, str) and _QUALITY_TENANT.fullmatch(tenant):
            entry["tenant"] = tenant
        entry.update({"poor": poor, "timestamp": time.time()})
        self._entries.append(entry)
        if len(self._entries) > self._max_size:
            self._entries.pop(0)
        return True

    def list(self, limit=20, only_poor=False):
        if type(limit) is not int or limit <= 0:
            return []
        entries = list(reversed(self._entries))
        if only_poor:
            entries = [e for e in entries if e["poor"]]
        return [dict(e) for e in entries[:min(limit, self._max_size)]]
