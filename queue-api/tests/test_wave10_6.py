from metrics import DailyMetrics

def test_cdr_dedupe_rejects_control_chars_in_correlated_fields():
    m = DailyMetrics(clock=lambda: 1700000000)
    base = {"Event":"Cdr","Disposition":"ANSWERED","Uniqueid":"1699999999.1","BillableSeconds":"60"}
    for change in ({"StartTime":"2026-01-01\nforged"}, {"Destination":"1001\rforged"}):
        m.apply_cdr_event({**base, **change})
    assert m.snapshot()["total_calls"] == 0
    m.apply_cdr_event({**base,"StartTime":"2026-01-01 12:00:00","Destination":"1001"})
    assert m.snapshot()["total_calls"] == 1
