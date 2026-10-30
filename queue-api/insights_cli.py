#!/usr/bin/env python3
"""CLI para 110 relatórios locais por tenant, sem chamadas ou APIs externas.

Uso:
 python3 queue-api/insights_cli.py --area calls --tenant t1 --file caminho/call_log.jsonl
 Áreas originais: calls, survey, pauses, campaigns.
 Áreas adicionais: calls_advanced, calls_trends, calls_audit,
 survey_advanced, pauses_advanced, campaigns_advanced,
 sla_history, quality_export, callbacks, unanswered, callback_aging,
 sla_capacity, presence, agent_efficiency, quality_advanced,
 cdr_integrity, callback_health e sla_risk.
Apenas leitura, filtra por empresa e omite dados de clientes no JSON.
Não faz validação de identidade ou permissão: execute no host autorizado.
"""
import argparse
import json
import sys

from insights_common import read_local_records, require_tenant
from insights_calls import (
    call_volume_by_day, call_answer_rate, call_missed_rate, call_talk_time,
    call_peak_day,
)
from insights_survey import (
    survey_average_rating, survey_rating_distribution, survey_positive_rate,
    survey_low_rating_rate, survey_daily_average,
)
from insights_pauses import (
    pause_total_time, pause_by_reason, pause_by_agent, pause_longest,
    pause_daily_trend,
)
from insights_campaigns import (
    campaign_status_breakdown, campaign_completion_rate, campaign_retry_pool,
    campaign_attempts_summary, campaign_agent_workload,
)

from insights_calls_advanced import (
    calls_disposition_breakdown, calls_volume_by_agent, calls_answered_by_agent,
    calls_talk_time_by_agent, calls_duration_bands,
)
from insights_calls_trends import (
    calls_weekday_volume, calls_weekly_volume, calls_monthly_volume,
    calls_monthly_answer_rate, calls_daily_answer_rate,
)
from insights_calls_audit import (
    calls_invalid_date_count, calls_missing_answered_duration,
    calls_unknown_disposition_count, calls_missing_operator_count,
    calls_negative_duration_conflicts,
)
from insights_survey_advanced import (
    survey_median_score, survey_score_by_agent, survey_neutral_rate,
    survey_weekly_response_count, survey_monthly_average,
)
from insights_pauses_advanced import (
    pause_average_duration, pause_median_duration, pause_duration_bands,
    pause_weekday_seconds, pause_active_agent_count,
)
from insights_campaigns_advanced import (
    campaigns_answered_share, campaigns_busy_share, campaigns_no_answer_share,
    campaigns_in_progress_count, campaigns_answered_by_agent,
)
from insights_sla_history import (
    sla_weighted_rate, sla_offered_by_day, sla_rate_by_queue,
    sla_days_below_eighty, sla_worst_day,
)
from insights_quality_export import (
    quality_average_jitter, quality_jitter_high_rate,
    quality_average_packet_loss, quality_average_rtt, quality_poor_by_agent,
)

from insights_callbacks import (
    callback_status_counts, callback_completion_rate, callback_attempt_distribution,
    callback_pending_per_day, callback_pending_retry_pool,
)
from insights_unanswered import (
    unanswered_reason_counts, unanswered_daily_volume, unanswered_by_agent,
    unanswered_monthly_volume, unanswered_daily_rate,
)

from insights_callback_aging import (
    callback_oldest_pending_seconds, callback_median_pending_seconds,
    callback_pending_age_bands, callback_pending_over_one_hour,
    callback_pending_created_weekday,
)
from insights_sla_capacity import (
    sla_out_of_target_by_queue, sla_monthly_weighted_rate,
    sla_most_loaded_queue, sla_weekday_weighted_rate,
    sla_latest_recorded_day,
)

from insights_presence import (
    presence_total_overrides, presence_by_status, presence_updated_by_day,
    presence_older_than_week, presence_missing_valid_timestamp,
)
from insights_agent_efficiency import (
    agent_answer_rate, agent_nonanswered_volume, agent_mean_talk_seconds,
    agent_median_talk_seconds, agent_over_five_minutes,
)

from insights_quality_advanced import (
    quality_p95_jitter, quality_p95_rtt, quality_high_loss_rate,
    quality_metric_coverage, quality_worst_agent_sample_rate,
)
from insights_cdr_integrity import (
    cdr_unknown_status_by_day, cdr_answered_zero_duration,
    cdr_nonanswered_with_billable, cdr_answered_missing_operator_rate,
    cdr_invalid_disposition_structure,
)
from insights_callback_health import (
    callback_pending_over_24h, callback_pending_over_48h,
    callback_pending_exhausted_attempts, callback_completed_by_attempts,
    callback_pending_share,
)
from insights_sla_risk import (
    sla_consecutive_days_below_eighty, sla_monthly_outside_target_count,
    sla_queue_traffic_share, sla_lowest_rate_queue_min_ten, sla_best_day,
)

FUNCTIONS = {
    "calls": (
        call_volume_by_day, call_answer_rate, call_missed_rate, call_talk_time,
        call_peak_day,
    ),
    "survey": (
        survey_average_rating, survey_rating_distribution, survey_positive_rate,
        survey_low_rating_rate, survey_daily_average,
    ),
    "pauses": (
        pause_total_time, pause_by_reason, pause_by_agent, pause_longest,
        pause_daily_trend,
    ),
    "campaigns": (
        campaign_status_breakdown, campaign_completion_rate, campaign_retry_pool,
        campaign_attempts_summary, campaign_agent_workload,
    ),
    "calls_advanced": (
        calls_disposition_breakdown, calls_volume_by_agent, calls_answered_by_agent,
        calls_talk_time_by_agent, calls_duration_bands,
    ),
    "calls_trends": (
        calls_weekday_volume, calls_weekly_volume, calls_monthly_volume,
        calls_monthly_answer_rate, calls_daily_answer_rate,
    ),
    "calls_audit": (
        calls_invalid_date_count, calls_missing_answered_duration,
        calls_unknown_disposition_count, calls_missing_operator_count,
        calls_negative_duration_conflicts,
    ),
    "survey_advanced": (
        survey_median_score, survey_score_by_agent, survey_neutral_rate,
        survey_weekly_response_count, survey_monthly_average,
    ),
    "pauses_advanced": (
        pause_average_duration, pause_median_duration, pause_duration_bands,
        pause_weekday_seconds, pause_active_agent_count,
    ),
    "campaigns_advanced": (
        campaigns_answered_share, campaigns_busy_share, campaigns_no_answer_share,
        campaigns_in_progress_count, campaigns_answered_by_agent,
    ),
    "sla_history": (
        sla_weighted_rate, sla_offered_by_day, sla_rate_by_queue,
        sla_days_below_eighty, sla_worst_day,
    ),
    "quality_export": (
        quality_average_jitter, quality_jitter_high_rate,
        quality_average_packet_loss, quality_average_rtt, quality_poor_by_agent,
    ),
    "callbacks": (
        callback_status_counts, callback_completion_rate, callback_attempt_distribution,
        callback_pending_per_day, callback_pending_retry_pool,
    ),
    "unanswered": (
        unanswered_reason_counts, unanswered_daily_volume, unanswered_by_agent,
        unanswered_monthly_volume, unanswered_daily_rate,
    ),
    "callback_aging": (
        callback_oldest_pending_seconds, callback_median_pending_seconds,
        callback_pending_age_bands, callback_pending_over_one_hour,
        callback_pending_created_weekday,
    ),
    "sla_capacity": (
        sla_out_of_target_by_queue, sla_monthly_weighted_rate,
        sla_most_loaded_queue, sla_weekday_weighted_rate,
        sla_latest_recorded_day,
    ),
    "presence": (
        presence_total_overrides, presence_by_status, presence_updated_by_day,
        presence_older_than_week, presence_missing_valid_timestamp,
    ),
    "agent_efficiency": (
        agent_answer_rate, agent_nonanswered_volume, agent_mean_talk_seconds,
        agent_median_talk_seconds, agent_over_five_minutes,
    ),
    "quality_advanced": (
        quality_p95_jitter, quality_p95_rtt, quality_high_loss_rate,
        quality_metric_coverage, quality_worst_agent_sample_rate,
    ),
    "cdr_integrity": (
        cdr_unknown_status_by_day, cdr_answered_zero_duration,
        cdr_nonanswered_with_billable, cdr_answered_missing_operator_rate,
        cdr_invalid_disposition_structure,
    ),
    "callback_health": (
        callback_pending_over_24h, callback_pending_over_48h,
        callback_pending_exhausted_attempts, callback_completed_by_attempts,
        callback_pending_share,
    ),
    "sla_risk": (
        sla_consecutive_days_below_eighty, sla_monthly_outside_target_count,
        sla_queue_traffic_share, sla_lowest_rate_queue_min_ten, sla_best_day,
    ),
}


def generate_report(area, tenant, records):
    """Executa cinco visões daquele domínio, sempre para um tenant exato."""
    require_tenant(tenant)
    if area not in FUNCTIONS:
        raise ValueError("área não permitida")
    functions = FUNCTIONS[area]
    result = {function.__name__: function(records, tenant) for function in functions}
    return {
        "schema_version": 1, "project": "AXE PABX",
        "scope": "local_readonly_per_tenant", "area": area, "tenant": tenant,
        "features_reported": len(result), "results": result,
        "operational_homologation_claimed": False,
        "access_control_enforced_by_cli": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--area", required=True, choices=sorted(FUNCTIONS))
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--file", required=True,
                        help="JSONL: chamadas/satisfacao/pausas/SLA; JSON array: campanhas/qualidade/callbacks; mapa JSON: presenca")
    args = parser.parse_args(argv)
    try:
        rows = read_local_records(
            args.file,
            collection=args.area in {"campaigns", "campaigns_advanced", "quality_export", "quality_advanced", "callbacks", "callback_aging", "callback_health"},
            keyed_entries=args.area == "presence",
        )
        report = generate_report(args.area, args.tenant, rows)
    except (OSError, ValueError, TypeError, UnicodeError, json.JSONDecodeError):
        # Nunca imprimir dados de registros ou caminhos sensíveis.
        print("Entrada inválida, não autorizada ou formato incompatível.", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
