from insights_pauses_advanced import pause_p95_duration

def test_pause_p95_uses_only_tenant_valid_durations():
    values=[{"extension":"t1-1001","duration_seconds":n,"reason":"descanso"} for n in range(1,21)]
    values.append({"extension":"t10-1001","duration_seconds":1000,"reason":"descanso"})
    assert pause_p95_duration(values,"t1") == {"measured_pauses":20,"p95_seconds":19.0}
    assert pause_p95_duration([],"t1") == {"measured_pauses":0,"p95_seconds":None}
