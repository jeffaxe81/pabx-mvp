"""Contrato dos 50 recursos analíticos do cockpit de voz."""
import copy
import math
import pytest

from call_center_cockpit import build_call_center_cockpit

VALUES = {
    "aguardando": 7, "filas_ativas": 2, "maior_espera": 121,
    "espera_media": 57, "espera_mediana": 59, "espera_p90": 121,
    "espera_p95": 121, "acima_limiar": 4, "acima_60s": 2,
    "acima_120s": 1, "faixa_0_19s": 2, "faixa_20_59s": 2,
    "faixa_60_119s": 1, "faixa_120s_mais": 2, "maior_backlog_fila": 5,
    "ramais_monitorados": 10, "ramais_livres": 2,
    "ramais_ocupados": 4, "ramais_tocando": 1,
    "ramais_indisponiveis": 2, "agentes_pausados": 2,
    "ausencias_manuais": 1, "percentual_livre": 20,
    "percentual_ocupado": 40, "percentual_indisponivel": 20,
    "percentual_pausado": 20, "percentual_ausente": 10,
    "espera_por_livre": 3.5, "reforco_referencia": 1,
    "sem_livres": 0, "oferecidas": 10, "dentro": 6,
    "fora": 4, "sla_percentual": 60, "sla_referencia": 80,
    "sla_desvio": -20, "percentual_fora": 40,
    "filas_abaixo_80": 1, "faltantes_ao_alvo": 2,
    "perfeitas_recuperacao": 10, "perdidas_buffer": 3,
    "fraude_buffer": 0, "qualidade_ruim_buffer": 1,
    "sinais_buffer": 4, "categorias_sinalizadas": 2,
    "alerta_fila": 1, "alerta_equipe": 0,
    "alerta_sla": 1, "alerta_qualidade": 1,
    "categorias_em_alerta": 3,
}


def summary(tenant="t1"):
    return {
        "scope": "memory_snapshot_tenant_only", "tenant": tenant, "metric_count": 20,
        "queues": {
            "waiting_calls": 7, "queues_with_waiting": 2,
            "waiting_above_sla_threshold": 4, "waiting_over_60_seconds": 2,
            "longest_wait_seconds": 121,
        },
        "extensions": {
            "monitored_extensions": 10, "free_extensions": 2,
            "busy_extensions": 4, "ringing_extensions": 1,
            "unavailable_extensions": 2,
        },
        "sla": {
            "offered_calls": 10, "within_sla_calls": 6,
            "outside_sla_calls": 4, "weighted_sla_percent": 60,
            "queues_below_reference_80": 1,
        },
        "observations": {
            "missed_events_in_buffer": 3, "fraud_alerts_in_buffer": 0,
            "poor_quality_samples_in_buffer": 1, "paused_agents_snapshot": 2,
            "manual_absent_overrides": 1,
        },
    }


def waiting():
    return [
        {"queue": ("fila-t1-en" if i >= 5 else "fila-t1"),
         "waiting_seconds": age,
         "channel": "PRIVATE-CALL-CH-%s" % i,
         "caller_id_num": "PRIVATE-555-123456"}
        for i, age in enumerate([0, 19, 20, 59, 60, 120, 121])
    ] + [
        {"queue": "fila-t2", "waiting_seconds": 9999,
         "caller_id_num": "PRIVATE-OTHER-TENANT"},
    ]


def cockpit(**overrides):
    kwargs = {"summary": summary(), "waiting": waiting(),
              "threshold_seconds": 20}
    kwargs.update(overrides)
    return build_call_center_cockpit("t1", **kwargs)


def test_contract_50_ids_unique_and_no_pii():
    result = cockpit()
    assert result["metric_count"] == 50
    assert [m["id"] for m in result["metrics"]] == [
        "CC-%02d" % i for i in range(1, 51)
    ]
    assert len({m["key"] for m in result["metrics"]}) == 50
    assert result["tenant"] == "t1"
    assert result["sla_reference_is_contractual"] is False
    assert result["production_homologation_claimed"] is False
    assert "PRIVATE-" not in str(result)
    assert "caller_id" not in str(result).lower()
    assert "channel" not in str(result).lower()


@pytest.mark.parametrize("key,expected", sorted(VALUES.items()))
def test_each_of_50_operational_indicators_has_expected_value(key, expected):
    result = cockpit()
    matched = [m for m in result["metrics"] if m["key"] == key]
    assert len(matched) == 1
    assert matched[0]["value"] == expected
    assert matched[0]["measured"] is True


def test_empty_samples_never_claim_good_sla_or_staffing():
    data = summary()
    data["sla"].update(offered_calls=0, within_sla_calls=0,
                       outside_sla_calls=0, weighted_sla_percent=None)
    data["extensions"] = {key: 0 for key in data["extensions"]}
    data["observations"]["paused_agents_snapshot"] = 0
    data["observations"]["manual_absent_overrides"] = 0
    result = cockpit(summary=data, waiting=[])
    by_key = {m["key"]: m["value"] for m in result["metrics"]}
    assert by_key["maior_espera"] is None
    assert by_key["espera_p90"] is None
    assert by_key["percentual_livre"] is None
    assert by_key["sla_percentual"] is None
    assert by_key["perfeitas_recuperacao"] is None
    assert by_key["alerta_equipe"] is None
    assert by_key["alerta_sla"] is None
    assert by_key["categorias_em_alerta"] is None
    assert by_key["aguardando"] == 0


def test_tenant_isolation_is_exact_not_prefix():
    data = summary("t1")
    other = {"queue": "fila-t10", "waiting_seconds": 86400,
             "caller_id_num": "PRIVATE-t10"}
    result = cockpit(summary=data, waiting=waiting() + [other])
    assert next(x["value"] for x in result["metrics"]
                if x["key"] == "aguardando") == 7
    assert "PRIVATE-t10" not in str(result)


@pytest.mark.parametrize("invalid", [None, "t2", "", "t10xx", "t0", "t1\n"])
def test_invalid_tenant_rejected(invalid):
    with pytest.raises(ValueError):
        build_call_center_cockpit(invalid, summary=summary(), waiting=[])


@pytest.mark.parametrize("invalid", [True, 0, -1, 3601, 20.5, "20"])
def test_invalid_threshold_rejected(invalid):
    with pytest.raises(ValueError):
        cockpit(threshold_seconds=invalid)


@pytest.mark.parametrize("age", [True, 2.5, -1, "40", math.inf,
                                  math.nan, 999_999_999])
def test_invalid_wait_age_rejected(age):
    with pytest.raises(ValueError):
        cockpit(waiting=[{"queue": "fila-t1", "waiting_seconds": age}])


def test_malformed_other_tenant_age_is_not_read_or_exposed():
    output = cockpit(waiting=waiting() + [
        {"queue": "fila-t2", "waiting_seconds": "PRIVATE"},
    ])
    assert output["metric_count"] == 50


@pytest.mark.parametrize("category,key,bad", [
    ("extensions", "free_extensions", True),
    ("extensions", "monitored_extensions", -1),
    ("sla", "offered_calls", "10"),
    ("sla", "within_sla_calls", math.inf),
    ("observations", "fraud_alerts_in_buffer", math.nan),
])
def test_invalid_aggregate_rejected(category, key, bad):
    sample = summary()
    sample[category][key] = bad
    with pytest.raises(ValueError):
        cockpit(summary=sample)


def test_contradictory_sla_and_extension_distribution_rejected():
    data = summary()
    data["sla"]["outside_sla_calls"] = 1
    with pytest.raises(ValueError):
        cockpit(summary=data)
    data = summary()
    data["extensions"]["free_extensions"] = 20
    with pytest.raises(ValueError):
        cockpit(summary=data)


def test_sample_below_10_has_unknown_sla_attention():
    data = summary()
    data["sla"].update(offered_calls=1, within_sla_calls=0,
                       outside_sla_calls=1)
    report = cockpit(summary=data)
    scores = {m["key"]: m["value"] for m in report["metrics"]}
    assert scores["alerta_sla"] is None
    assert scores["categorias_em_alerta"] is None


def test_boundary_threshold_uses_strictly_greater_than():
    result = cockpit(waiting=[
        {"queue": "fila-t1", "waiting_seconds": 20},
        {"queue": "fila-t1", "waiting_seconds": 21},
    ])
    values = {m["key"]: m["value"] for m in result["metrics"]}
    assert values["acima_limiar"] == 1
    assert values["faixa_20_59s"] == 2
