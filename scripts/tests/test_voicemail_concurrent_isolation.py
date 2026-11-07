"""Negativas para inspeção simultânea do VoiceMailMain no Asterisk real."""
from lab.voicemail_checks import inspected_voicemail_channel


def channel(endpoint, tenant, *, mailbox=None, extension="*97",
            context=None, state="Up", app="VoiceMailMain", cid="00000001"):
    mailbox = endpoint + "@" + tenant if mailbox is None else mailbox
    context = tenant + "-internal" if context is None else context
    return ("PJSIP/" + endpoint + "-" + cid + "!" + context
            + "!" + extension + "!3!" + state + "!" + app + "!" + mailbox
            + "!100.1")


def test_concurrent_legitimate_mailboxes_are_accepted_without_prefix_match():
    own = channel("t1-1001", "t1")
    other = channel("t10-1001", "t10", cid="00000002")
    assert inspected_voicemail_channel(own + "\n" + other, "t1-1001", "t1") == {
        "exact": True, "no_foreign": True
    }


def test_foreign_voicemail_channel_with_wrong_dialplan_denies_full_proof():
    own = channel("t1-1001", "t1")
    for other in (
        channel("t2-1001", "t2", extension="1010"),
        channel("t2-1001", "t2", state="Ring"),
        channel("t2-1001", "t2", context="t1-internal"),
        channel("t2-1001", "t2", mailbox="t1-1001@t1"),
        channel("t10-1001", "t10", mailbox="t1-1001@t1"),
    ):
        result = inspected_voicemail_channel(
            own + "\n" + other, "t1-1001", "t1")
        assert result == {"exact": True, "no_foreign": False}


def test_duplicate_same_extension_never_combines_voicemail_evidence():
    own = channel("t1-1001", "t1")
    repeated = channel("t1-1001", "t1", cid="00000002")
    result = inspected_voicemail_channel(
        own + "\n" + repeated, "t1-1001", "t1")
    assert result == {"exact": False, "no_foreign": False}


def test_invalid_or_oversized_capture_is_rejected_fail_closed():
    for bad in (None, [], "x" * (1024 * 1024 + 1), ""):
        assert inspected_voicemail_channel(bad, "t1-1001", "t1") == {
            "exact": False, "no_foreign": False
        }
