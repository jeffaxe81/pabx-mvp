"""Contratos do laboratório: framing real e segredos fora do checkout."""
import hashlib
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def test_tcp_framing_retains_next_response_and_waits_for_body():
    from lab.sip_tls import pop_message
    first = b'SIP/2.0 200 OK\r\nContent-Length: 3\r\n\r\nabc'
    second = b'SIP/2.0 401 Unauthorized\r\nContent-Length: 0\r\n\r\n'
    assert pop_message(first[:-1]) == (None, first[:-1])
    message, rest = pop_message(first + second)
    assert message == first
    assert rest == second


def test_sip_framing_rejects_invalid_and_oversized_lengths():
    from lab.sip_tls import pop_message
    for length in ('-1', 'abc', '99999999'):
        with pytest.raises(ValueError):
            pop_message(f'SIP/2.0 200 OK\r\nContent-Length: {length}\r\n\r\n'.encode())
    with pytest.raises(ValueError):
        pop_message(b'x' * 65537)
    with pytest.raises(ValueError):
        pop_message(b'SIP/2.0 200 OK\r\nContent-Length: 0\r\nContent-Length: 1\r\n\r\nx')


def test_digest_matches_rfc2617_known_vector():
    from lab.sip_tls import digest_authorization
    # Vetor RFC 2617, calculado independentemente do gerador SIP.
    value = digest_authorization(
        'Digest realm="testrealm@host.com", qop="auth,auth-int", '
        'nonce="dcd98b7102dd2f0e8b11d0f600bfb0c093", opaque="5ccc069c403ebaf9f0171e9517f40e41"',
        username='Mufasa', password='Circle Of Life', method='GET',
        uri='/dir/index.html', cnonce='0a4f113b',
    )
    assert 'response="6629fae49393a05397450978507c4ef1"' in value
    assert 'qop=auth' in value
    assert 'nc=00000001' in value
    assert 'opaque="5ccc069c403ebaf9f0171e9517f40e41"' in value


def test_digest_rejects_unsupported_algorithm_and_qop():
    from lab.sip_tls import digest_authorization
    for challenge in ('Basic realm="a"', 'Digest realm="a",nonce="b",algorithm=SHA-999',
                      'Digest realm="a",nonce="b",qop="auth-int"', 'Digest realm="a"'):
        with pytest.raises(ValueError):
            digest_authorization(challenge, username='u', password='p', method='REGISTER', uri='sip:localhost')


def test_private_lab_copy_rotates_secrets_and_preserves_source(tmp_path):
    from lab.asterisk_lab import prepare
    before = (ROOT / 'asterisk/pjsip.conf').read_bytes()
    prepared = prepare(ROOT, tmp_path / 'private')
    assert (ROOT / 'asterisk/pjsip.conf').read_bytes() == before
    conf = (tmp_path / 'private/asterisk/pjsip.conf').read_text()
    assert 'troque_esta_senha' not in conf
    assert 'bind=0.0.0.0' not in conf
    assert len(prepared['credentials']['t1-1001']) >= 24
    assert len(set(prepared['credentials'].values())) == len(prepared['credentials'])
    assert (tmp_path / 'private').stat().st_mode & 0o077 == 0
    assert (tmp_path / 'private/asterisk/pjsip.conf').stat().st_mode & 0o077 == 0
    assert (tmp_path / 'private/asterisk/pjsip_tenants/t3.conf').exists()


def test_sip_client_rejects_non_loopback_target_before_connecting(tmp_path):
    from lab.sip_tls import SipTLS
    with pytest.raises(ValueError):
        SipTLS('example.com', 5061, tmp_path/'ca.crt', 'user', 'secret')
