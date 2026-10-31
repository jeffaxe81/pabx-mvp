import pytest
from insights_callback_aging import (
    callback_oldest_pending_seconds, callback_median_pending_seconds,
    callback_pending_age_bands, callback_pending_over_one_hour,
    callback_pending_created_weekday,
)

def _rows():
    return [{"id":"a1", "tenant":"t1", "status":"pendente", "attempts":0, "requested_at":1000},
            {"id":"a2", "tenant":"t1", "status":"pendente", "attempts":1, "requested_at":4700},
            {"id":"b1", "tenant":"t10","status":"pendente", "attempts":0, "requested_at":1000}]

def test_callback_aging_is_reproducible_at_cutoff():
    records = _rows()
    assert callback_oldest_pending_seconds(records,"t1",as_of=4600) == {
        "pending_with_valid_date":1,"oldest_seconds":3600}
    assert callback_median_pending_seconds(records,"t1",as_of=4600)["median_seconds"] == 3600
    assert callback_pending_age_bands(records,"t1",as_of=4600)["over_2h"] == 0
    assert callback_pending_over_one_hour(records,"t1",as_of=4600)["at_least_one_hour"] == 1
    assert sum(callback_pending_created_weekday(records,"t1",as_of=4600).values()) == 1

def test_callback_aging_refuses_invalid_cutoff():
    for invalid in (float("nan"), True, -1, "4600"):
        with pytest.raises(ValueError):
            callback_oldest_pending_seconds(_rows(),"t1",as_of=invalid)
