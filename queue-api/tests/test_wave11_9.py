from insights_sla_risk import sla_best_day

def test_best_sla_day_prefers_broader_sample_when_rates_equal():
    records = [
      {"queue":"fila-t1", "date":"2026-10-20", "offered":1, "within_sla":1},
      {"queue":"fila-t1", "date":"2026-10-21", "offered":100, "within_sla":100},
      {"queue":"fila-t1", "date":"2026-10-22", "offered":25, "within_sla":20},
      {"queue":"fila-t10", "date":"2026-10-19", "offered":1000, "within_sla":1000}]
    result = sla_best_day(records, "t1")
    assert result == {"date":"2026-10-21", "sla_percent":100.0, "offered":100}

def test_best_sla_day_ties_choose_earlier_date():
    r = [{"queue":"fila-t2", "date":d, "offered":10, "within_sla":8}
         for d in ("2026-10-23", "2026-10-22")]
    assert sla_best_day(r,"t2")["date"] == "2026-10-22"
