"""Fail-closed correlation of outbound AMI events.

Originate.ActionID tracks the request, while Originate.ChannelId gives
the first Asterisk channel a deterministic Uniqueid. DialEnd may refer
to the originating channel via Uniqueid or DestUniqueid. No matching
number alone can prove a particular attempt.
"""
import re

ATTEMPT_RE = re.compile(r"^[0-9a-f]{32}$")


def channel_id_for(attempt_id):
    if not isinstance(attempt_id, str) or not ATTEMPT_RE.fullmatch(attempt_id):
        return None
    return "axe-" + attempt_id


def matches_dial_event(event, record):
    """Only a matching channel Uniqueid OR explicitly correlated test/event.

    If AMI supplied channel IDs, a contradictory ID wins over an
    AttemptID hint and the result is rejected. For older synthetic
    integrations without channel IDs, a matching explicit AttemptID
    is still supported; a destination phone by itself is never enough.
    """
    if not isinstance(event, dict) or not isinstance(record, dict):
        return False
    attempt_id = record.get("attempt_id")
    channel_id = record.get("channel_id")
    if channel_id_for(attempt_id) != channel_id:
        return False
    hint = event.get("AttemptID")
    if hint is not None and hint != attempt_id:
        return False
    channel_ids = [event.get(key) for key in ("Uniqueid", "DestUniqueid")
                   if event.get(key) is not None]
    if channel_ids:
        return channel_id in channel_ids
    return hint == attempt_id


def matches_originate_response(event, record):
    if not isinstance(event, dict) or event.get("Event") != "OriginateResponse":
        return False
    if event.get("Response") not in {"Success", "Failure"}:
        return False
    attempt = record.get("attempt_id") if isinstance(record, dict) else None
    channel_id = channel_id_for(attempt)
    if channel_id is None or record.get("channel_id") != channel_id:
        return False
    if event.get("ActionID") != attempt or event.get("Uniqueid") != channel_id:
        return False
    # Account code is optional on OriginateResponse but must not
    # contradict the record if it is present.
    for key in ("AccountCode", "Accountcode"):
        value = event.get(key)
        if value is not None and value != record.get("tenant"):
            return False
    return True
