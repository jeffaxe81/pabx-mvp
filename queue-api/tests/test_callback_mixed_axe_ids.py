"""DialEnd: nenhuma tentativa externa pode mascarar um canal AXE correto."""
from outbound_correlation import matches_dial_event

ATTEMPT = "a" * 32
CHANNEL = "axe-" + ATTEMPT
OTHER = "axe-" + "b" * 32
RECORD = {"attempt_id": ATTEMPT, "channel_id": CHANNEL}


def test_channel_id_must_be_exact_and_dialend_can_include_normal_destination():
    assert matches_dial_event({"Uniqueid": CHANNEL}, RECORD)
    assert matches_dial_event({"DestUniqueid": CHANNEL}, RECORD)
    assert matches_dial_event({
        "Uniqueid": CHANNEL, "DestUniqueid": "1792670400.99"
    }, RECORD)
    assert matches_dial_event({"AttemptID": ATTEMPT}, RECORD)


def test_other_axe_attempt_cannot_share_dialend_or_bypass_via_hint():
    for event in (
        {"Uniqueid": CHANNEL, "DestUniqueid": OTHER},
        {"Uniqueid": OTHER, "DestUniqueid": CHANNEL},
        {"Uniqueid": CHANNEL, "DestUniqueid": ["malformed"]},
        {"Uniqueid": CHANNEL, "DestUniqueid": {"id": OTHER}},
        {"Uniqueid": CHANNEL, "DestUniqueid": "x\ninjected"},
        {"Uniqueid": CHANNEL, "DestUniqueid": "x" * 97},
        {"Uniqueid": CHANNEL, "AttemptID": "b" * 32},
    ):
        assert not matches_dial_event(event, RECORD)
    assert not matches_dial_event({
        "Uniqueid": OTHER, "AttemptID": ATTEMPT
    }, RECORD)


def test_matching_hint_never_substitutes_foreign_channel():
    assert not matches_dial_event({
        "Uniqueid": OTHER, "DestUniqueid": "1792670400.88",
        "AttemptID": ATTEMPT,
    }, RECORD)
    assert not matches_dial_event({
        "Uniqueid": CHANNEL, "DestUniqueid": OTHER, "AttemptID": ATTEMPT,
    }, RECORD)
    assert not matches_dial_event({}, RECORD)


def test_dialend_actionid_is_optional_but_must_not_contradict_attempt():
    assert matches_dial_event({"Uniqueid": CHANNEL, "ActionID": ATTEMPT}, RECORD)
    assert matches_dial_event({"Uniqueid": CHANNEL}, RECORD)
    for action in ("b" * 32, "invalid", 1, [], {"id": ATTEMPT}):
        assert not matches_dial_event({
            "Uniqueid": CHANNEL, "DestUniqueid": "1792670400.1",
            "AttemptID": ATTEMPT, "ActionID": action,
        }, RECORD)
    assert not matches_dial_event({
        "ActionID": "b" * 32, "AttemptID": ATTEMPT
    }, RECORD)
