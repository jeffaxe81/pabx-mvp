from insights_calls_trends import calls_monthly_answer_rate, calls_daily_answer_rate, calls_weekly_volume

def test_answer_rate_does_not_count_unknown_status_as_missed():
    rows = [{"tenant":"t1","date":"2026-10-30","disposition":status}
            for status in ("ANSWERED","BUSY","BROKEN")]
    rows += [{"tenant":"t10","date":"2026-10-30","disposition":"ANSWERED"}]
    assert calls_daily_answer_rate(rows,"t1")["2026-10-30"] == {
        "answered":1, "total":2, "rate_percent":50.0}
    assert calls_monthly_answer_rate(rows,"t1")["2026-10"] == {
        "answered":1, "total":2, "rate_percent":50.0}
    assert sum(calls_weekly_volume(rows, "t1").values()) == 3
