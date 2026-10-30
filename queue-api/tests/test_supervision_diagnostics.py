"""Regressão dos vinte diagnósticos operacionais, sem tráfego real."""
import math

import pytest

from supervision_diagnostics import RULES, evaluate_supervision_diagnostics


def fixture_summary():
    return {
        "scope": "memory_snapshot_tenant_only", "tenant": "t1",
        "metric_count": 20,
        "queues": {
            "waiting_calls": 12, "queues_with_waiting": 4,
            "waiting_above_sla_threshold": 3, "waiting_over_60_seconds": 1,
            "longest_wait_seconds": 200,
        },
        "extensions": {
            "monitored_extensions": 10, "free_extensions": 0,
            "ringing_extensions": 5, "busy_extensions": 9,
            "unavailable_extensions": 3,
        },
        "sla": {
            "offered_calls": 20, "within_sla_calls": 5,
            "outside_sla_calls": 15, "weighted_sla_percent": 25,
            "queues_below_reference_80": 2,
        },
        "observations": {
            "missed_events_in_buffer": 12, "fraud_alerts_in_buffer": 1,
            "poor_quality_samples_in_buffer": 3,
            "paused_agents_snapshot": 5, "manual_absent_overrides": 5,
        },
    }


def test_all_twenty_rules_are_unique_and_actionable():
    assert len(RULES) == 20
    assert len({r[0] for r in RULES}) == 20
    assert [r[0] for r in RULES] == [f"OP-{i:02d}" for i in range(1, 21)]
    report = evaluate_supervision_diagnostics(fixture_summary())
    assert report["rule_count"] == 20
    assert report["tenant"] == "t1"
    assert report["attention_count"] == 18
    assert report["normal_count"] == 2
    assert report["unknown_count"] == 0
    assert {r["status"] for r in report["rules"]} == {"attention", "normal"}
    assert all(r["reference_is_contractual"] is False for r in report["rules"])
    assert report["operational_homologation_claimed"] is False
    assert "caller_id" not in str(report).lower()


def test_missing_measurements_are_unknown_not_false_green():
    summary = fixture_summary()
    summary["queues"] = {
        key: None if key == "longest_wait_seconds" else 0
        for key in summary["queues"]
    }
    summary["extensions"] = {key: 0 for key in summary["extensions"]}
    summary["sla"] = {key: None if key == "weighted_sla_percent" else 0
                      for key in summary["sla"]}
    summary["observations"] = {key: 0 for key in summary["observations"]}
    report = evaluate_supervision_diagnostics(summary)
    rules = {r["rule_id"]: r["status"] for r in report["rules"]}
    assert rules["OP-05"] == "unknown"
    assert rules["OP-06"] == "attention"
    assert rules["OP-07"] == "unknown"
    assert rules["OP-09"] == "unknown"
    assert all(rules[f"OP-{i:02d}"] == "unknown" for i in range(11, 16))
    assert rules["OP-16"] == "normal"
    assert report["unknown_count"] >= 8


@pytest.mark.parametrize("invalid", [None, [], {}, {"scope": "forged"},
                                     {"scope": "memory_snapshot_tenant_only", "metric_count": 20}])
def test_invalid_summary_fails_closed(invalid):
    with pytest.raises(ValueError):
        evaluate_supervision_diagnostics(invalid)


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"),
                                 -1, "10", [], {}, 100_000_001])
def test_invalid_measurement_does_not_become_healthy(bad):
    summary = fixture_summary()
    summary["queues"]["waiting_calls"] = bad
    result = evaluate_supervision_diagnostics(summary)
    assert result["rules"][0]["status"] == "unknown"
    assert result["rules"][0]["observed"] is None


def test_unknown_when_sla_volume_below_minimum_and_ratio_at_threshold():
    summary = fixture_summary()
    summary["sla"]["offered_calls"] = 9
    summary["sla"]["within_sla_calls"] = 6
    summary["sla"]["outside_sla_calls"] = 3
    summary["sla"]["weighted_sla_percent"] = 66.7
    report = evaluate_supervision_diagnostics(summary)
    statuses = {r["rule_id"]: r["status"] for r in report["rules"]}
    assert statuses["OP-12"] == "unknown"
    assert statuses["OP-15"] == "unknown"
    summary["sla"]["offered_calls"] = 10
    summary["sla"]["outside_sla_calls"] = 3
    statuses = {r["rule_id"]: r["status"]
                for r in evaluate_supervision_diagnostics(summary)["rules"]}
    assert statuses["OP-15"] == "attention"


def test_diagnostics_can_only_describe_auth_scope_not_read_private_data():
    summary = fixture_summary()
    summary["tenant"] = "t10"
    summary["queues"]["caller_id_num"] = "PRIVATE-55551111"
    summary["observations"]["other_tenant_data"] = "PRIVATE-t1"
    result = evaluate_supervision_diagnostics(summary)
    assert result["tenant"] == "t10"
    assert "PRIVATE-" not in str(result)
    assert "other_tenant_data" not in str(result)
