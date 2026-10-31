import pytest
from insights_presence import presence_older_than_week

def test_presence_age_reproducible_and_scope_exact():
    rows=[{"extension":"t1-1001","status":"disponivel","updated_at":100},
          {"extension":"t1-1002","status":"ausente","updated_at":700000},
          {"extension":"t10-1001","status":"ausente","updated_at":100}]
    p=presence_older_than_week(rows,"t1",as_of=700000)
    assert p=={"measured_overrides":2,"seven_days_or_older":1,
               "seven_days_or_older_percent":50.0}
    for value in (True,float("nan"),-1,"700000"):
        with pytest.raises(ValueError):
            presence_older_than_week(rows,"t1",as_of=value)
