"""Cockpit de voz: 50 indicadores operacionais de leitura, sem controle AMI.

Não é CDR financeiro nem substitui homologação de SLA. Usa exclusivamente
dados já observados pelo queue-api. Nunca retorna CallerID, canal, ramal,
Uniqueid, motivo de pausa, número de cliente ou eventos individuais.
Os indicadores 23-29 e 39-40 são estimativas/heurísticas, não fatos SIP.
"""
from collections import Counter
from math import ceil, isfinite
import re
import statistics

from pickup import queue_tenant

TENANT_RE = re.compile(r"t[1-9][0-9]*\Z")
TARGET_SLA = 80
MAX_WAIT_SECONDS = 86400 * 30
MAX_WAITING = 10000


def _valid_number(value):
    return (type(value) in (int, float) and isfinite(value)
            and 0 <= value <= 100_000_000)


def _count(section, key):
    value = section.get(key)
    if type(value) is not int or value < 0 or value > 10_000_000:
        raise ValueError("contador operacional invalido")
    return value


def _percentage(numerator, denominator):
    return round(numerator * 100 / denominator, 2) if denominator > 0 else None


def _percentile(values, percentile):
    """Percentil determinístico, nearest-rank (bom para filas pequenas)."""
    return values[ceil(percentile * len(values)) - 1] if values else None


def _risk(value):
    # None representa insuficiência de dados, não 'sem risco'.
    return None if value is None else int(bool(value))


def build_call_center_cockpit(tenant, *, summary, waiting,
                              threshold_seconds=20):
    """Calcula exatamente cinquenta KPIs distintos no escopo do tenant.

    O estado de fila é memória volátil; indicações de dimensionamento
    assumem máximo de 3 aguardando por posição livre como REFERÊNCIA.
    """
    if (not isinstance(tenant, str) or not TENANT_RE.fullmatch(tenant)
            or not isinstance(summary, dict)
            or summary.get("scope") != "memory_snapshot_tenant_only"
            or summary.get("tenant") != tenant
            or summary.get("metric_count") != 20
            or type(threshold_seconds) is not int
            or not 1 <= threshold_seconds <= 3600
            or not isinstance(waiting, list)
            or len(waiting) > MAX_WAITING):
        raise ValueError("fonte operacional invalida")
    sections = {}
    for key in ("queues", "extensions", "sla", "observations"):
        if not isinstance(summary.get(key), dict):
            raise ValueError("secao operacional ausente")
        sections[key] = summary[key]
    q, agents, sla, observations = (sections[s] for s in
                                    ("queues", "extensions", "sla", "observations"))
    # Não confiar em identificadores de tenant fornecidos na query nem
    # em linhas arbitrárias: filtrar novamente pelo nome da fila.
    ages = []
    depths = Counter()
    for row in waiting:
        if not isinstance(row, dict):
            raise ValueError("linha de fila invalida")
        queue = row.get("queue")
        if queue_tenant(queue) != tenant:
            continue
        age = row.get("waiting_seconds")
        if type(age) is not int or not 0 <= age <= MAX_WAIT_SECONDS:
            raise ValueError("espera invalida")
        ages.append(age)
        depths[queue] += 1
    ages.sort()
    backlog = len(ages)
    monitored = _count(agents, "monitored_extensions")
    free = _count(agents, "free_extensions")
    busy = _count(agents, "busy_extensions")
    ringing = _count(agents, "ringing_extensions")
    unavailable = _count(agents, "unavailable_extensions")
    paused = _count(observations, "paused_agents_snapshot")
    absent = _count(observations, "manual_absent_overrides")
    offered = _count(sla, "offered_calls")
    within = _count(sla, "within_sla_calls")
    outside = _count(sla, "outside_sla_calls")
    below = _count(sla, "queues_below_reference_80")
    missed = _count(observations, "missed_events_in_buffer")
    fraud = _count(observations, "fraud_alerts_in_buffer")
    poor = _count(observations, "poor_quality_samples_in_buffer")
    if within > offered or outside != offered - within:
        raise ValueError("SLA contraditorio")
    # Extensões podem monitorar ramais comuns, não apenas agentes.
    # Por isso, as taxas se referem explicitamente a ramais monitorados.
    if any(n > monitored for n in (free, busy, ringing, unavailable)):
        raise ValueError("estado de ramais contraditorio")
    if sum((free, busy, ringing, unavailable)) > monitored:
        raise ValueError("estados de ramais sobrepostos")
    metrics = []
    def add(category, name, title, value, unit):
        if value is not None and type(value) not in (int, float):
            raise ValueError("valor de KPI invalido")
        if value is not None and not isfinite(value):
            raise ValueError("valor nao finito")
        metrics.append({
            "id": "CC-%02d" % (len(metrics) + 1),
            "category": category, "key": name, "label": title,
            "value": value, "unit": unit,
            "measured": value is not None,
        })

    # 01-15: fila, idades, percentis e distribuição de espera.
    add("fila", "aguardando", "Chamadas aguardando", backlog, "chamadas")
    add("fila", "filas_ativas", "Filas com espera", len(depths), "filas")
    add("fila", "maior_espera", "Maior espera", ages[-1] if ages else None, "s")
    add("fila", "espera_media", "Espera média", round(statistics.mean(ages), 2) if ages else None, "s")
    add("fila", "espera_mediana", "Mediana de espera", round(statistics.median(ages), 2) if ages else None, "s")
    add("fila", "espera_p90", "Espera P90", _percentile(ages, .9), "s")
    add("fila", "espera_p95", "Espera P95", _percentile(ages, .95), "s")
    add("fila", "acima_limiar", "Espera acima do limite SLA", sum(x > threshold_seconds for x in ages), "chamadas")
    add("fila", "acima_60s", "Espera acima de 60 s", sum(x > 60 for x in ages), "chamadas")
    add("fila", "acima_120s", "Espera acima de 120 s", sum(x > 120 for x in ages), "chamadas")
    add("fila", "faixa_0_19s", "Espera de 0 a 19 s", sum(x < 20 for x in ages), "chamadas")
    add("fila", "faixa_20_59s", "Espera de 20 a 59 s", sum(20 <= x < 60 for x in ages), "chamadas")
    add("fila", "faixa_60_119s", "Espera de 60 a 119 s", sum(60 <= x < 120 for x in ages), "chamadas")
    add("fila", "faixa_120s_mais", "Espera de 120 s ou mais", sum(x >= 120 for x in ages), "chamadas")
    add("fila", "maior_backlog_fila", "Maior fila por volume", max(depths.values(), default=0), "chamadas")

    # 16-30: capacidade aproximada de atendimento usando hints e pausas.
    add("equipe", "ramais_monitorados", "Ramais monitorados", monitored, "ramais")
    add("equipe", "ramais_livres", "Ramais livres", free, "ramais")
    add("equipe", "ramais_ocupados", "Ramais ocupados", busy, "ramais")
    add("equipe", "ramais_tocando", "Ramais tocando", ringing, "ramais")
    add("equipe", "ramais_indisponiveis", "Ramais indisponíveis", unavailable, "ramais")
    add("equipe", "agentes_pausados", "Agentes pausados", paused, "agentes")
    add("equipe", "ausencias_manuais", "Ausências manuais", absent, "ramais")
    add("equipe", "percentual_livre", "Participação livre", _percentage(free, monitored), "%")
    add("equipe", "percentual_ocupado", "Participação ocupada", _percentage(busy, monitored), "%")
    add("equipe", "percentual_indisponivel", "Participação indisponível", _percentage(unavailable, monitored), "%")
    add("equipe", "percentual_pausado", "Pausas por ramal monitorado (aprox.)", _percentage(paused, monitored), "%")
    add("equipe", "percentual_ausente", "Ausências por ramal monitorado (aprox.)", _percentage(absent, monitored), "%")
    add("equipe", "espera_por_livre", "Fila por ramal livre", round(backlog / free, 2) if free else None, "chamadas/ramal")
    add("equipe", "reforco_referencia", "Reforço sugerido (3 por ramal)", max(0, ceil(backlog / 3) - free), "ramais")
    add("equipe", "sem_livres", "Fila sem ramais livres", int(backlog > 0 and free == 0), "sinal")

    # 31-40: SLA observado e conta conservadora de recuperação da meta.
    rate = _percentage(within, offered)
    delta = round(rate - TARGET_SLA, 2) if rate is not None else None
    missing_now = max(0, ceil(TARGET_SLA * offered / 100) - within)
    perfect_to_recover = max(0, ceil((TARGET_SLA * offered - 100 * within) / (100 - TARGET_SLA)))
    add("sla", "oferecidas", "Chamadas oferecidas", offered, "chamadas")
    add("sla", "dentro", "Chamadas dentro do SLA", within, "chamadas")
    add("sla", "fora", "Chamadas fora do SLA", outside, "chamadas")
    add("sla", "sla_percentual", "SLA observado", rate, "%")
    add("sla", "sla_referencia", "SLA de referência", TARGET_SLA, "%")
    add("sla", "sla_desvio", "Diferença para referência", delta, "p.p.")
    add("sla", "percentual_fora", "Percentual fora do SLA", _percentage(outside, offered), "%")
    add("sla", "filas_abaixo_80", "Filas abaixo de 80%", below, "filas")
    add("sla", "faltantes_ao_alvo", "Atendimentos faltantes no volume atual", missing_now, "chamadas")
    add("sla", "perfeitas_recuperacao", "Próximas chamadas perfeitas para recuperar 80%", perfect_to_recover if offered else None, "chamadas")

    # 41-45: sinais observados, sem transformar buffers em taxa contratual.
    add("qualidade", "perdidas_buffer", "Eventos perdidos no buffer", missed, "eventos")
    add("qualidade", "fraude_buffer", "Alertas de fraude no buffer", fraud, "alertas")
    add("qualidade", "qualidade_ruim_buffer", "Medições de qualidade ruim", poor, "amostras")
    add("qualidade", "sinais_buffer", "Soma de sinais nos buffers", missed + fraud + poor, "sinais")
    add("qualidade", "categorias_sinalizadas", "Categorias de risco com sinais", sum(x > 0 for x in (missed, fraud, poor)), "categorias")

    # 46-50: diagnósticos binários não acionam bloqueio nem mudanças na fila.
    queue_risk = _risk(backlog >= 10 or any(x > 120 for x in ages))
    staffing_risk = _risk(backlog > 0 and free == 0) if monitored else None
    sla_risk = _risk(rate < TARGET_SLA) if offered >= 10 else None
    quality_risk = _risk(fraud > 0 or poor > 0)
    known = (queue_risk, staffing_risk, sla_risk, quality_risk)
    overall = None if any(x is None for x in known) else sum(known)
    add("diagnostico", "alerta_fila", "Atenção na fila", queue_risk, "sinal")
    add("diagnostico", "alerta_equipe", "Atenção à equipe", staffing_risk, "sinal")
    add("diagnostico", "alerta_sla", "Atenção ao SLA", sla_risk, "sinal")
    add("diagnostico", "alerta_qualidade", "Atenção à qualidade", quality_risk, "sinal")
    add("diagnostico", "categorias_em_alerta", "Categorias em alerta", overall, "categorias")
    if len(metrics) != 50 or len({m["key"] for m in metrics}) != 50:
        raise RuntimeError("contrato de 50 indicadores violado")
    return {
        "schema_version": 1, "tenant": tenant,
        "scope": "tenant_memory_snapshot_only", "metric_count": 50,
        "sla_reference_is_contractual": False,
        "staffing_recommendation_is_heuristic": True,
        "production_homologation_claimed": False,
        "snapshot_cannot_reconstruct_cdr_history": True,
        "sla_threshold_seconds": threshold_seconds,
        "metrics": metrics,
    }
