"""Pacotes reais em UDP loopback: negociação, autenticação e conteúdo."""
import base64
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def test_secure_sdp_exposes_only_loopback_and_requires_valid_sdes_key():
    from lab.srtp_media import SrtpMedia, parse_sdp
    peer = SrtpMedia()
    try:
        address, key = parse_sdp(peer.offer())
        assert address == ('127.0.0.1', peer.port)
        assert len(key) == 30
        for old, new in [('127.0.0.1', '192.0.2.1'), ('RTP/SAVP', 'RTP/AVP'),
                         ('AES_CM_128_HMAC_SHA1_80', 'AES_CM_128_HMAC_SHA1_32'),
                         ('m=audio ', 'm=video '), (' 0\r\n', ' 8\r\n')]:
            with pytest.raises(ValueError):
                parse_sdp(peer.offer().replace(old.encode(), new.encode()))
        with pytest.raises(ValueError):
            parse_sdp(peer.offer().replace(base64.b64encode(peer.key), b'bad!'))
        with pytest.raises(ValueError):
            parse_sdp(peer.offer() + b'm=audio 3333 RTP/SAVP 0\r\n')
    finally:
        peer.close()


def test_srtp_sends_and_authenticates_distinct_pcmu_both_directions():
    from lab.srtp_media import SrtpMedia, exchange
    left, right = SrtpMedia(), SrtpMedia()
    try:
        left.negotiate(right.offer())
        right.negotiate(left.offer())
        result = exchange(left, right, duration=0.3)
        assert result['left_received'] >= 5
        assert result['right_received'] >= 5
        assert result['payloads_match'] is True
        assert result['authenticated'] is True
        assert result['tamper_rejected'] is True
        assert result['replay_rejected'] is True
    finally:
        left.close()
        right.close()


def test_srtp_rejects_adulterated_packet_and_replay():
    import pylibsrtp
    from lab.srtp_media import SrtpMedia
    left, right = SrtpMedia(), SrtpMedia()
    try:
        right.negotiate(left.offer())
        packet = left.protect(b'\xff' * 160)
        with pytest.raises(pylibsrtp.Error):
            right.unprotect(packet[:-1] + bytes([packet[-1] ^ 1]))
        assert right.unprotect(packet)[12:] == b'\xff' * 160
        with pytest.raises(pylibsrtp.Error):
            right.unprotect(packet)
    finally:
        left.close()
        right.close()


def test_sdp_rejects_remote_media_override_and_key_lifetime():
    from lab.srtp_media import SrtpMedia, parse_sdp
    peer = SrtpMedia()
    try:
        for suffix in (b'c=IN IP4 192.0.2.9\r\n', b'a=sendonly\r\n'):
            with pytest.raises(ValueError):
                parse_sdp(peer.offer() + suffix)
        with pytest.raises(ValueError):
            parse_sdp(peer.offer().replace(b'\r\na=sendrecv', b'|2^20\r\na=sendrecv'))
    finally:
        peer.close()


def test_sdp_selects_pcmu_from_asterisk_codec_offer_and_preserves_crypto_tag():
    from lab.srtp_media import SrtpMedia, parse_sdp
    local, remote = SrtpMedia(), SrtpMedia()
    try:
        offer = remote.offer().replace(b'RTP/SAVP 0\r\n', b'RTP/SAVP 0 8 107 101\r\n')
        offer = offer.replace(b'a=crypto:1 ', b'a=crypto:7 ')
        offer += b'a=rtpmap:8 PCMA/8000\r\na=rtpmap:107 opus/48000/2\r\na=rtpmap:101 telephone-event/8000\r\n'
        assert parse_sdp(offer) == (('127.0.0.1', remote.port), remote.key)
        local.negotiate(offer)
        assert b'RTP/SAVP 0\r\n' in local.offer()
        assert b'a=crypto:7 AES_CM_128_HMAC_SHA1_80 ' in local.offer()
    finally:
        local.close()
        remote.close()

def test_rfc4733_srtp_negotiation_rejects_missing_or_spoofed_telephone_event():
    from lab.srtp_media import SrtpMedia
    caller, callee = SrtpMedia(dtmf=True), SrtpMedia(dtmf=True)
    try:
        assert b'RTP/SAVP 0 101' in caller.offer()
        assert b'a=rtpmap:101 telephone-event/8000' in caller.offer()
        plain = SrtpMedia()
        try:
            with pytest.raises(ValueError, match='DTMF'):
                caller.negotiate(plain.offer())
        finally:
            plain.close()
        spoofed = callee.offer().replace(
            b'101 telephone-event/8000', b'101 PCMU/8000')
        with pytest.raises(ValueError, match='DTMF'):
            caller.negotiate(spoofed)
        caller.negotiate(callee.offer())
        callee.negotiate(caller.offer())
    finally:
        caller.close()
        callee.close()


def test_rfc4733_pin_digits_are_srtp_protected_and_never_echoed():
    import struct
    from lab.srtp_media import SrtpMedia
    caller, callee = SrtpMedia(dtmf=True), SrtpMedia(dtmf=True)
    try:
        caller.negotiate(callee.offer())
        callee.negotiate(caller.offer())
        caller.send_dtmf('#')
        packets = []
        callee.socket.settimeout(2)
        for _ in range(9):
            packet, address = callee.socket.recvfrom(4096)
            assert address == caller.socket.getsockname()
            decrypted = callee.unprotect(packet)
            packets.append(decrypted)
        assert all((p[1] & 0x7f) == 101 for p in packets)
        assert packets[0][1] & 0x80
        assert all(p[12] == 11 for p in packets)  # codigo RFC4733 de '#'
        assert all((p[13] & 0x80) == 0 for p in packets[:6])
        assert all((p[13] & 0x80) != 0 for p in packets[6:])
        assert len({struct.unpack('!I', p[4:8])[0] for p in packets}) == 1
        assert [struct.unpack('!H', p[2:4])[0] for p in packets] == list(
            range(struct.unpack('!H', packets[0][2:4])[0],
                  struct.unpack('!H', packets[0][2:4])[0] + 9)
        ) or (
            len({struct.unpack('!H', p[2:4])[0] for p in packets}) == 9
            and ((struct.unpack('!H', packets[-1][2:4])[0] -
                  struct.unpack('!H', packets[0][2:4])[0]) & 65535) == 8
        )
    finally:
        caller.close()
        callee.close()


@pytest.mark.parametrize('digit', ['', 'x', '99', None, 4, [], {}, 'secret'])
def test_rfc4733_rejects_unsupported_digit_without_emitting_payload(digit):
    from lab.srtp_media import SrtpMedia
    peer = SrtpMedia(dtmf=True)
    try:
        with pytest.raises(ValueError):
            peer.protect_dtmf(digit, duration=160)
        with pytest.raises(ValueError):
            peer.protect_dtmf('1', duration=True)
        with pytest.raises(ValueError):
            peer.protect_dtmf('1', duration=65536)
    finally:
        peer.close()
