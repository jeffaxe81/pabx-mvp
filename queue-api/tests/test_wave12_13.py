from insights_calls import call_answer_rate, call_volume_by_day

def test_call_reports_ignore_status_with_control_characters():
    records=[{"tenant":"t1","date":"2026-10-31","disposition":"ANSWERED"},
             {"tenant":"t1","date":"2026-10-31","disposition":"ANSWERED\nforged"},
             {"tenant":"t10","date":"2026-10-31","disposition":"ANSWERED"}]
    assert call_answer_rate(records,"t1")=={
        "answered":1,"total":1,"answer_rate_percent":100.0}
    assert call_volume_by_day(records,"t1")=={"2026-10-31":1}
