#!/usr/bin/env python3
"""CLI para 20 relatórios locais por tenant, sem chamadas ou APIs externas.

Uso:
 python3 queue-api/insights_cli.py --area calls --tenant t1 --file caminho/call_log.jsonl
 Áreas: calls, survey, pauses, campaigns.
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
                        help="calls/survey/pauses: JSONL local; campaigns: array JSON")
    args = parser.parse_args(argv)
    try:
        rows = read_local_records(args.file, collection=args.area == "campaigns")
        report = generate_report(args.area, args.tenant, rows)
    except (OSError, ValueError, TypeError, UnicodeError, json.JSONDecodeError):
        # Nunca imprimir dados de registros ou caminhos sensíveis.
        print("Entrada inválida, não autorizada ou formato incompatível.", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
