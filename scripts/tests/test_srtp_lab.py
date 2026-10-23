"""SRTP real em UDP loopback; sem Asterisk simulado e sem gravações publicadas."""
import base64
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import threading

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def sdp(*, ip='127.0.0.1', port=15000, protocol='RTP/SAVP', key=None):
    key = base64.b64encode(bytes(range(30))).decode() if key is None else key
    return (f'v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\ns=Private test\r\n'
            f'c=IN IP4 {ip}\r\nt=0 0\r\nm=audio {port} {protocol} 0\r\n'
            f'a=crypto:1 AES_CM_128_HMAC_SHA1_80 inline:{key}\r\n'
            'a=rtpmap:0 PCMU/8000\r\na=sendrecv\r\n').encode()


def test_secure_sdp_accepts_only_pcmu_srtp_and_does_not_expose_key_in_repr():
    from lab.srtp_media import parse_sdes
    result = parse_sdes(sdp())
    assert result.address == ('127.0.0.1', 15000)
    assert result.tag == '1'
    assert result.key == bytes(range(30))
    assert base64.b64encode(bytes(range(30))).decode() not in repr(result)
    assert 'key=' not in repr(result)


@pytest.mark.parametrize('body', [
    sdp(ip='192.0.2.1'), sdp(ip='localhost'), sdp(port=0), sdp(port=70000),
    sdp(protocol='RTP/AVP'), sdp(key='not-base64'),
    sdp(key=base64.b64encode(b'short').decode()),
    sdp().replace(b'AES_CM_128_HMAC_SHA1_80', b'AES_CM_128_HMAC_SHA1_32'),
    sdp()+b'm=audio 16000 RTP/SAVP 0\r\n',
    sdp().replace(b' 0\r\n', b' 8\r\n'),
    sdp().replace(b'a=sendrecv', b'a=inactive'),
], ids=['external-ip','hostname','zero-port','large-port','plain-rtp','bad-base64',
         'short-key','weak-profile','two-media','no-pcmu','inactive'])
def test_insecure_or_ambiguous_sdp_is_rejected(body):
    from lab.srtp_media import parse_sdes
    with pytest.raises(ValueError):
        parse_sdes(body)


def test_two_real_udp_peers_exchange_authenticated_srtp_and_receive_expected_audio():
    from lab.srtp_media import SrtpMedia
    a, b = SrtpMedia(b'\x55'*160), SrtpMedia(b'\xaa'*160)
    try:
        a.negotiate(b.offer())
        b.negotiate(a.offer())
        gate = threading.Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            ra = pool.submit(a.exchange, b'\xaa'*160, gate)
            rb = pool.submit(b.exchange, b'\x55'*160, gate)
            results = [ra.result(timeout=8), rb.result(timeout=8)]
        for result in results:
            assert result['sent'] >= 40
            assert result['received_expected'] >= 20
            assert result['encrypted_wire'] is True
            assert result['wrong_key_rejected'] is True
            assert result['success'] is True
            assert 'key' not in result
    finally:
        a.close()
        b.close()


def test_no_incoming_media_cannot_be_reported_as_success():
    from lab.srtp_media import SrtpMedia
    a, b = SrtpMedia(b'\x55'*160), SrtpMedia(b'\xaa'*160)
    try:
        a.negotiate(b.offer())
        result = a.exchange(b'\xaa'*160, None, packets=5)
        assert result['sent'] == 5
        assert result['received_expected'] == 0
        assert result['success'] is False
    finally:
        a.close()
        b.close()
