"""Diálogo SIP e evidência CDR: fixtures de protocolo, sem PABX fictício aprovado."""
import csv
import io
from pathlib import Path
import queue
import re
import socket
import sys
import threading

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def test_invite_challenge_and_success_are_acknowledged_before_authenticated_bye():
    from lab.call_peer import CallPeer
    from lab.sip_tls import parse_message, pop_message
    from lab.srtp_media import SrtpMedia
    client, server = socket.socketpair()
    client.settimeout(3)
    server.settimeout(3)
    peer = CallPeer.__new__(CallPeer)
    peer.connection, peer.buffer, peer.port = client, b'', 55001
    peer.username, peer.password, peer.target_port = 't1-1202', 'private-fixture', 5061
    media = SrtpMedia(b'\x55'*160)
    remote = SrtpMedia(b'\xaa'*160)
    errors, seen = queue.Queue(), []

    def serve():
        pending = b''
        def read():
            nonlocal pending
            while True:
                raw, pending = pop_message(pending)
                if raw is not None:
                    message = parse_message(raw)
                    seen.append(message)
                    return message
                packet = server.recv(8192)
                if not packet:
                    raise RuntimeError('cliente encerrou antes do fim do diálogo')
                pending += packet
        def respond(code, reason, headers, tag, body=b'', extra=''):
            text = (f'SIP/2.0 {code} {reason}\r\n'
                    f'Via: {headers["via"][0]}\r\nFrom: {headers["from"][0]}\r\n'
                    f'To: <sip:1201@localhost>;tag={tag}\r\n'
                    f'Call-ID: {headers["call-id"][0]}\r\nCSeq: {headers["cseq"][0]}\r\n'
                    'Contact: <sip:127.0.0.1:5061;transport=tls>\r\n'+extra+
                    ('Content-Type: application/sdp\r\n' if body else '')+
                    f'Content-Length: {len(body)}\r\n\r\n')
            server.sendall(text.encode()+body)
        try:
            _, first, _ = read()
            respond(401, 'Unauthorized', first, 'challenge',
                    extra='WWW-Authenticate: Digest realm="asterisk", nonce="abcdef", algorithm=MD5, qop="auth"\r\n')
            read()  # ACK não final
            _, authenticated, _ = read()
            respond(200, 'OK', authenticated, 'dialog', body=remote.offer())
            read()  # ACK final
            _, bye, _ = read()
            respond(200, 'OK', bye, 'dialog')
        except BaseException as exc:
            errors.put(exc)
        finally:
            server.close()
    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    try:
        assert peer.invite('1201', media) is True
        assert peer.hangup() is True
        worker.join(4)
        assert not worker.is_alive()
        if not errors.empty():
            raise errors.get()
        assert [item[0].split()[0] for item in seen] == ['INVITE','ACK','INVITE','ACK','BYE']
        assert [item[1]['cseq'][0] for item in seen] == ['1 INVITE','1 ACK','2 INVITE','2 ACK','3 BYE']
        assert seen[0][1]['via'] == seen[1][1]['via']
        assert seen[2][1]['via'] != seen[3][1]['via']
        assert 'authorization' in seen[2][1]
        assert seen[3][1]['to'][0].endswith(';tag=dialog')
        assert seen[4][0] == 'BYE sip:127.0.0.1:5061;transport=tls SIP/2.0'
    finally:
        client.close()
        media.close()
        remote.close()
        worker.join(4)


def cdr_line(*, tenant='t1', caller='1202', target='1201', context='t1-internal', disposition='ANSWERED', uid='call-current', billsec='2'):
    output = io.StringIO()
    csv.writer(output).writerow([tenant,caller,target,context,'caller',
                               'PJSIP/t1-1202-00001','PJSIP/t1-1201-00002','Dial','PJSIP/t1-1201',
                               '2026-10-23 10:00:00','2026-10-23 10:00:01','2026-10-23 10:00:03',
                               '3',billsec,disposition,'DOCUMENTATION',uid,''])
    return output.getvalue()


def test_answered_cdr_must_match_current_call_tenant_context_and_direction():
    from lab.call_lab import cdr_matches
    assert cdr_matches(cdr_line(), tenant='t1', caller='1202', target='1201', unique_id='call-current')
    assert not cdr_matches(cdr_line(tenant='t2'), tenant='t1', caller='1202', target='1201', unique_id='call-current')
    assert not cdr_matches(cdr_line(context='t2-internal'), tenant='t1', caller='1202', target='1201', unique_id='call-current')
    assert not cdr_matches(cdr_line(uid='call-old'), tenant='t1', caller='1202', target='1201', unique_id='call-current')
    assert not cdr_matches(cdr_line(disposition='NO ANSWER'), tenant='t1', caller='1202', target='1201', unique_id='call-current')
    assert not cdr_matches(cdr_line(billsec='0'), tenant='t1', caller='1202', target='1201', unique_id='call-current')
    assert not cdr_matches(cdr_line(), tenant='t1', caller='1201', target='1202', unique_id='call-current')


def test_old_or_duplicate_cdr_cannot_approve_current_call():
    from lab.call_lab import cdr_matches
    assert not cdr_matches('', tenant='t1', caller='1202', target='1201', unique_id='call-current')
    assert not cdr_matches(cdr_line()*2, tenant='t1', caller='1202', target='1201', unique_id='call-current')
    assert not cdr_matches(cdr_line(uid='old'), tenant='t1', caller='1202', target='1201', unique_id='call-current')


def test_active_channel_unique_id_requires_exact_tenant_caller_and_target():
    from lab.call_lab import active_unique_id
    line = 'PJSIP/t1-1202-0000000a!t1-internal!1201!3!Up!Dial!PJSIP/t1-1201,20!1202!t1!3!2!bridge!1792750000.2\n'
    assert active_unique_id(line, tenant='t1', caller='1202', target='1201') == '1792750000.2'
    assert active_unique_id(line, tenant='t2', caller='1202', target='1201') is None
    assert active_unique_id(line, tenant='t1', caller='1201', target='1202') is None
    assert active_unique_id(line+line, tenant='t1', caller='1202', target='1201') is None
    assert active_unique_id('partial!row', tenant='t1', caller='1202', target='1201') is None


def test_call_endpoints_use_private_real_generator_for_both_tenants(tmp_path):
    from lab.asterisk_lab import prepare
    from lab.call_lab import provision_call_endpoints
    prepared = prepare(ROOT, tmp_path/'private')
    provision_call_endpoints(ROOT, 'HEAD', prepared)
    conf = prepared['conf']
    for tenant in ('t1','t2'):
        for number in ('1201','1202'):
            name = tenant+'-'+number
            assert len(prepared['credentials'][name]) >= 32
            assert f'[{name}](endpoint-secure)' in (conf/'generated/pjsip_dynamic.conf').read_text()
        dialplan = (conf/f'generated/extensions_dynamic_dial-{tenant}.conf').read_text()
        assert 'exten => 1201,1,' in dialplan
        assert f'Set(CDR(accountcode)={tenant})' in dialplan
    assert (conf/'generated/pjsip_dynamic.conf').stat().st_mode & 0o077 == 0
