from insights_common import percent

def test_percent_does_not_convert_corrupt_counters_to_business_metrics():
    for part,total in ((3,0),(5,4),(-1,3),(True,3),(1,True),
                       (float("nan"),2),(1,float("inf")),(None,2)):
        assert percent(part,total) == 0.0
    assert percent(3,4) == 75.0
    assert percent(0,7) == 0.0
