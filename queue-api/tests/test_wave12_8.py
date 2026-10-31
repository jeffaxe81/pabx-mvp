from insights_pauses import pause_daily_trend, pause_total_time

def test_nonfinite_pause_timestamp_is_not_turned_into_a_date():
    rows=[{"extension":"t1-1001","reason":"descanso","duration_seconds":10,
           "started_at":float("nan")},
          {"extension":"t1-1002","reason":"descanso","duration_seconds":20,
           "started_at":float("inf")}]
    assert pause_daily_trend(rows,"t1") == {}
    assert pause_total_time(rows,"t1") == {"pauses":2,"total_seconds":30.0}
