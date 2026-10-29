"""Private runtime evidence cannot mix channels, tenants or expose PINs."""
from pathlib import Path
import struct
import sys
import socket

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def test_prompt_evidence_is_exact_channel_scoped_and_contains_no_secrets():
    from lab.voicemail_auth_checks import inspect_auth_prompts
    channel = 'PJSIP/t1-1001-00000001'
    raw = "\n".join((
        f"-- <{channel}> Playing 'vm-password.slin' (language 'en')",
        "-- <PJSIP/t10-1001-00000001> Playing 'vm-youhave.slin' (language 'en')",
        "Incorrect password '93847261' for user 't1-1001' (context = t1)",
        f"-- <{channel}> Playing 'vm-incorrect.slin' (language 'en')",
    ))
    result = inspect_auth_prompts(raw, channel, 't1')
    assert result == {'password_prompts': 1, 'incorrect_prompts': 1,
                      'authenticated_intro': False, 'goodbye': False,
                      'own_message': False, 'foreign_message': False}
    assert '93847261' not in repr(result)


@pytest.mark.parametrize('path, own, foreign', [
    ('/var/spool/asterisk/voicemail/t1/t1-1001/INBOX/msg0000', True, False),
    ('/var/spool/asterisk/voicemail/t10/t10-1001/INBOX/msg0000', False, True),
    ('/var/spool/asterisk/voicemail/t1/t1-1002/INBOX/msg0000', False, True),
])
def test_message_evidence_requires_exact_tenant_and_endpoint(path, own, foreign):
    from lab.voicemail_auth_checks import inspect_auth_prompts
    raw = f"-- <PJSIP/t1-1001-a> Playing '{path}.wav' (language 'en')"
    result = inspect_auth_prompts(raw, 'PJSIP/t1-1001-a', 't1')
    assert result['own_message'] is own
    assert result['foreign_message'] is foreign


def test_parser_rejects_bad_scope_instead_of_accepting_other_tenant_intro():
    from lab.voicemail_auth_checks import inspect_auth_prompts
    for channel, tenant in [('PJSIP/t10-1001-a', 't1'), ('x', 't1')]:
        with pytest.raises(ValueError, match='escopo'):
            inspect_auth_prompts('', channel, tenant)
    with pytest.raises(ValueError):
        inspect_auth_prompts('x' * (2 * 1024 * 1024 + 1), 'PJSIP/t1-1001-a', 't1')


def test_rfc4733_events_are_encrypted_and_keep_fixed_timestamp_until_end():
    from lab.voicemail_auth_checks import VoicemailMedia
    from lab.srtp_media import SrtpMedia
    sender, receiver = VoicemailMedia(), SrtpMedia()
    try:
        offer = sender.offer()
        assert b'RTP/SAVP 0 101\r\n' in offer
        assert b'a=rtpmap:101 telephone-event/8000\r\n' in offer
        assert b'a=fmtp:101 0-16\r\n' in offer
        receiver.negotiate(offer)
        start = sender.timestamp
        packets = [sender.protect_event('5', duration=n, end=e, marker=m)
                   for n, e, m in [(160, False, True), (320, False, False),
                                   (1280, True, False), (1280, True, False)]]
        plain = [receiver.unprotect(p) for p in packets]
        assert [p[1] for p in plain] == [229, 101, 101, 101]
        assert [struct.unpack('!I', p[4:8])[0] for p in plain] == [start] * 4
        assert [p[12:] for p in plain] == [b'\x05\x0a\x00\xa0', b'\x05\x0a\x01\x40',
                                          b'\x05\x8a\x05\x00', b'\x05\x8a\x05\x00']
        assert all(p[12:] != wire[12:] for p, wire in zip(plain, packets))
        with pytest.raises(ValueError):
            sender.protect_event('t1-1001', duration=160)
    finally:
        sender.close()
        receiver.close()


def test_digit_transport_sends_authenticated_event_end_redundancy_and_advances_clock():
    from lab.voicemail_auth_checks import VoicemailMedia
    sender, receiver = VoicemailMedia(), VoicemailMedia()
    try:
        sender.negotiate(receiver.offer())
        receiver.negotiate(sender.offer())
        receiver.socket.settimeout(0.3)
        start = sender.timestamp
        sender.send_digits('8#')
        received = []
        while True:
            try:
                packet, address = receiver.socket.recvfrom(4096)
            except socket.timeout:
                break
            assert address == ('127.0.0.1', sender.port)
            received.append(receiver.unprotect(packet))
        assert len(received) == 22
        assert [p[12] for p in received[:11]] == [8] * 11
        assert [p[12] for p in received[11:]] == [11] * 11
        assert [bool(p[13] & 128) for p in received[:11]] == [False] * 8 + [True] * 3
        assert struct.unpack('!I', received[0][4:8])[0] == start
        assert struct.unpack('!I', received[11][4:8])[0] == (start + 2080) & 0xffffffff
        assert sender.timestamp == (start + 4160) & 0xffffffff
        with pytest.raises(ValueError):
            sender.send_digits('')
        with pytest.raises(ValueError):
            sender.send_digits('8\r\n')
    finally:
        sender.close()
        receiver.close()


def test_dtmf_negotiation_rejects_missing_or_remapped_telephone_events():
    from lab.voicemail_auth_checks import VoicemailMedia
    from lab.srtp_media import SrtpMedia
    local, remote = VoicemailMedia(), SrtpMedia()
    try:
        for answer in (remote.offer(), local.offer().replace(
                b'telephone-event/8000', b'opus/48000')):
            with pytest.raises(ValueError, match='DTMF'):
                local.negotiate(answer)
            assert local.address is None
            assert local.rx is None
    finally:
        local.close()
        remote.close()
