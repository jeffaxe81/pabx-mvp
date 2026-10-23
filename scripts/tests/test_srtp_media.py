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
