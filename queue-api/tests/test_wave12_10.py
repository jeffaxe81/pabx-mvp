from insights_sla_history import sla_days_below_eighty

def test_sla_below_eighty_uses_exact_counters():
    records=[{"queue":"fila-t1","date":"2026-10-29","offered":10000,"within_sla":7996},
             {"queue":"fila-t1","date":"2026-10-30","offered":100,"within_sla":80},
             {"queue":"fila-t10","date":"2026-10-29","offered":100,"within_sla":0}]
    assert sla_days_below_eighty(records,"t1")=={
        "days_measured":2,"days_below_80_percent":1}
