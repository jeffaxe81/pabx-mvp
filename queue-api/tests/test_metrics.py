from metrics import DailyMetrics

DAY_1 = 1_700_000_000        # timestamp fixo qualquer (dia 1)
DAY_1_LATER = DAY_1 + 3600    # mesmo dia, 1h depois
DAY_2 = DAY_1 + 90000         # bem mais de 24h depois (dia seguinte)


def make_clock(sequence):
    """Clock de teste: cada chamada retorna o próximo valor da lista."""
    values = list(sequence)

    def clock():
        return values.pop(0) if len(values) > 1 else values[0]

    return clock


def test_starts_zeroed():
    metrics = DailyMetrics(clock=lambda: DAY_1)
    snapshot = metrics.snapshot()
    assert snapshot["total_calls"] == 0
    assert snapshot["answered_calls"] == 0
    assert snapshot["missed_calls"] == 0
    assert snapshot["average_talk_seconds"] == 0
    assert snapshot["missed_rate_percent"] == 0


def test_answered_call_counts_toward_total_and_talk_time():
    metrics = DailyMetrics(clock=lambda: DAY_1)
    metrics.apply_cdr_event({"Event": "Cdr", "Disposition": "ANSWERED", "BillableSeconds": "120"})

    snapshot = metrics.snapshot()
    assert snapshot["total_calls"] == 1
    assert snapshot["answered_calls"] == 1
    assert snapshot["missed_calls"] == 0
    assert snapshot["average_talk_seconds"] == 120


def test_missed_call_counts_toward_total_but_not_talk_time():
    metrics = DailyMetrics(clock=lambda: DAY_1)
    metrics.apply_cdr_event({"Event": "Cdr", "Disposition": "NO ANSWER", "BillableSeconds": "0"})

    snapshot = metrics.snapshot()
    assert snapshot["total_calls"] == 1
    assert snapshot["answered_calls"] == 0
    assert snapshot["missed_calls"] == 1


def test_average_talk_time_across_multiple_calls():
    metrics = DailyMetrics(clock=lambda: DAY_1)
    metrics.apply_cdr_event({"Event": "Cdr", "Disposition": "ANSWERED", "BillableSeconds": "100"})
    metrics.apply_cdr_event({"Event": "Cdr", "Disposition": "ANSWERED", "BillableSeconds": "200"})

    assert metrics.snapshot()["average_talk_seconds"] == 150


def test_missed_rate_percent_calculation():
    metrics = DailyMetrics(clock=lambda: DAY_1)
    metrics.apply_cdr_event({"Event": "Cdr", "Disposition": "ANSWERED", "BillableSeconds": "60"})
    metrics.apply_cdr_event({"Event": "Cdr", "Disposition": "ANSWERED", "BillableSeconds": "60"})
    metrics.apply_cdr_event({"Event": "Cdr", "Disposition": "NO ANSWER", "BillableSeconds": "0"})
    metrics.apply_cdr_event({"Event": "Cdr", "Disposition": "BUSY", "BillableSeconds": "0"})

    snapshot = metrics.snapshot()
    assert snapshot["total_calls"] == 4
    assert snapshot["missed_rate_percent"] == 50.0


def test_ignores_non_cdr_events():
    metrics = DailyMetrics(clock=lambda: DAY_1)
    metrics.apply_cdr_event({"Event": "Hangup"})
    metrics.apply_cdr_event({"Event": "QueueCallerJoin"})

    assert metrics.snapshot()["total_calls"] == 0


def test_ignores_cdr_event_without_disposition():
    metrics = DailyMetrics(clock=lambda: DAY_1)
    metrics.apply_cdr_event({"Event": "Cdr"})
    assert metrics.snapshot()["total_calls"] == 0


def test_handles_missing_or_invalid_billable_seconds_gracefully():
    metrics = DailyMetrics(clock=lambda: DAY_1)
    metrics.apply_cdr_event({"Event": "Cdr", "Disposition": "ANSWERED"})  # sem BillableSeconds
    metrics.apply_cdr_event({"Event": "Cdr", "Disposition": "ANSWERED", "BillableSeconds": "abc"})

    snapshot = metrics.snapshot()
    assert snapshot["answered_calls"] == 2
    assert snapshot["average_talk_seconds"] == 0


def test_resets_on_new_day():
    clock_value = [DAY_1]
    metrics = DailyMetrics(clock=lambda: clock_value[0])

    metrics.apply_cdr_event({"Event": "Cdr", "Disposition": "ANSWERED", "BillableSeconds": "100"})
    assert metrics.snapshot()["total_calls"] == 1

    clock_value[0] = DAY_2
    snapshot = metrics.snapshot()
    assert snapshot["total_calls"] == 0
    assert snapshot["average_talk_seconds"] == 0


def test_does_not_reset_within_the_same_day():
    clock_value = [DAY_1]
    metrics = DailyMetrics(clock=lambda: clock_value[0])

    metrics.apply_cdr_event({"Event": "Cdr", "Disposition": "ANSWERED", "BillableSeconds": "100"})
    clock_value[0] = DAY_1_LATER
    metrics.apply_cdr_event({"Event": "Cdr", "Disposition": "ANSWERED", "BillableSeconds": "50"})

    snapshot = metrics.snapshot()
    assert snapshot["total_calls"] == 2
    assert snapshot["average_talk_seconds"] == 75


def test_billable_seconds_never_credits_negative_fractional_or_huge_values():
    metrics = DailyMetrics(clock=lambda: DAY_1)
    for value in ("-30", -1, True, 3.5, "1.2", "1e9", "99999999999", [], {}):
        metrics.apply_cdr_event({"Event": "Cdr", "Disposition": "ANSWERED",
                                 "BillableSeconds": value})
    metrics.apply_cdr_event({"Event": "Cdr", "Disposition": "ANSWERED",
                             "BillableSeconds": "120"})
    report = metrics.snapshot()
    assert report["answered_calls"] == 10
    assert report["average_talk_seconds"] == 12.0


def test_valid_seconds_accept_zero_and_integer_without_truncation():
    metrics = DailyMetrics(clock=lambda: DAY_1)
    for value in (0, 2, "3"):
        metrics.apply_cdr_event({"Event": "Cdr", "Disposition": "ANSWERED",
                                 "BillableSeconds": value})
    assert metrics.snapshot()["average_talk_seconds"] == 1.7


def test_non_dict_cdr_does_not_crash_daily_metrics():
    metrics = DailyMetrics(clock=lambda: DAY_1)
    for event in (None, [], False, "Cdr"):
        metrics.apply_cdr_event(event)
    assert metrics.snapshot()["total_calls"] == 0


def test_cdr_disposition_malformed_never_inflates_totals():
    metrics = DailyMetrics(clock=lambda: DAY_1)
    for bad in ([], {}, True, 1, "", "X" * 33, "ANSWERED" + chr(10)):
        metrics.apply_cdr_event({"Event": "Cdr", "Disposition": bad})
    assert metrics.snapshot()["total_calls"] == 0
