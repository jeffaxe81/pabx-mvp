from fraud_detection import compute_daily_cost, is_over_spending_limit

def test_corrupt_cdr_does_not_inflate_spending():
    rows = [None, "ignored", {"disposition":"ANSWERED","billable_seconds":True},
            {"disposition":"ANSWERED","billable_seconds":-1},
            {"disposition":"ANSWERED","billable_seconds":float("inf")},
            {"disposition":"ANSWERED","billable_seconds":120},
            {"disposition":"NO ANSWER","billable_seconds":1000}]
    assert compute_daily_cost(rows, 0.5) == 1.0
    assert is_over_spending_limit(rows, 0.5, 0.9)
    assert not is_over_spending_limit(rows, 0.5, 1.1)

def test_cost_rate_and_limit_must_be_finite_and_typed():
    assert compute_daily_cost([], float("nan")) == 0.0
    assert compute_daily_cost(None, 1) == 0.0
    assert compute_daily_cost([{"disposition":"ANSWERED","billable_seconds":60}], -1) == 0.0
    for limit in (float("nan"), float("inf"), True, None):
        assert not is_over_spending_limit([], 1, limit)
