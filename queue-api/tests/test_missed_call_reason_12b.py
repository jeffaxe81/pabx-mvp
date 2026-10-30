from missed_calls import MissedCallsLog

def test_direct_history_insert_sanitizes_reason_and_source():
    log = MissedCallsLog()
    assert log.append({"caller_id_num":"123","reason":"BUSY\nFake","source":["dial"]})
    row = log.list()[0]
    assert row["reason"] == ""
    assert row["source"] == ""
    assert row["caller_id_num"] == "123"

def test_valid_dial_reason_is_unchanged():
    log = MissedCallsLog()
    log.append({"caller_id_num":"123","reason":"NOANSWER","source":"dial"})
    assert log.list()[0]["reason"] == "NOANSWER"
