"""Synthetic negative checks for the diagnostic AMI Local/ trace parser.

These fixtures never claim Asterisk runtime evidence and never dial a phone.
"""
import sys
from pathlib import Path

import pytest

# This suite runs with working-directory=scripts in the static matrix. Add the
# repository root explicitly so it exercises the same lab parser used by the
# Asterisk workflow instead of depending on the runner's implicit PYTHONPATH.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lab.ami_live_checks import assess_local_dial_trace


CHANNEL = "axe-" + "a" * 32


def event(kind, account="t1", uniqueid=CHANNEL, dest="local-target", linked=CHANNEL, **extra):
    return {"Event": kind, "AccountCode": account, "Uniqueid": uniqueid,
            "DestUniqueid": dest, "Linkedid": linked, **extra}


def test_observation_only_when_identity_chain_is_consistent():
    report = assess_local_dial_trace([
        event("DialBegin"), event("DialEnd", DialStatus="ANSWER")
    ], CHANNEL)
    assert report == {
        "dial_begin_observed": True,
        "dial_end_observed": True,
        "dial_pair_identity_consistent": True,
        "origin_channel_in_dial_trace": True,
        "dial_answer_observed": True,
        "local_probe_only": True,
    }


@pytest.mark.parametrize("broken", [
    event("DialEnd", account="t2", DialStatus="ANSWER"),
    event("DialEnd", uniqueid="other", DialStatus="ANSWER"),
    event("DialEnd", dest="other", DialStatus="ANSWER"),
    event("DialEnd", linked="other", DialStatus="ANSWER"),
    event("DialEnd", linked="", DialStatus="ANSWER"),
    event("DialEnd", DialStatus="NOT_A_STATUS"),
])
def test_inconsistent_or_untrusted_dialend_is_not_proof_of_answer(broken):
    outcome = assess_local_dial_trace([event("DialBegin"), broken], CHANNEL)
    assert outcome["dial_end_observed"]
    assert not outcome["dial_answer_observed"]


def test_no_dialend_never_claims_answer():
    observation = assess_local_dial_trace([event("DialBegin")], CHANNEL)
    assert not observation["dial_end_observed"]
    assert not observation["dial_pair_identity_consistent"]
    assert not observation["dial_answer_observed"]


def test_same_number_or_unrelated_channel_cannot_reconcile():
    outcome = assess_local_dial_trace([
        event("DialBegin", uniqueid="one", dest="two", linked="three"),
        event("DialEnd", uniqueid="one", dest="two", linked="three",
              DialStatus="ANSWER"),
    ], CHANNEL)
    assert not outcome["origin_channel_in_dial_trace"]
    assert not outcome["dial_pair_identity_consistent"]
    assert not outcome["dial_answer_observed"]
    assert outcome["local_probe_only"]
