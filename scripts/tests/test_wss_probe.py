"""Handshake TLS/WebSocket real em loopback, incluindo controles negativos."""
import base64
from contextlib import contextmanager
import hashlib
import socket
import ssl
import subprocess
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))


@pytest.fixture
def certificate(tmp_path):
    cert,key=tmp_path/'ca.crt',tmp_path/'key.pem'
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),
                    '-out',str(cert),'-days','1','-subj','/CN=localhost','-addext',
                    'subjectAltName=DNS:localhost,IP:127.0.0.1'],check=True,capture_output=True)
    return cert,key


@contextmanager
def wss_server(certificate, *, wrong_accept=False, wrong_protocol=False):
    listener=socket.socket()
    listener.bind(('127.0.0.1',0));listener.listen();listener.settimeout(4)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(*map(str,certificate))
    errors=[]
    def serve():
        try:
            raw,_=listener.accept()
            try:
                with context.wrap_socket(raw,server_side=True) as connection:
                    data=b''
                    while b'\r\n\r\n' not in data: data+=connection.recv(8192)
                    request=data.decode('ascii')
                    assert request.startswith('GET /ws HTTP/1.1\r\n')
                    assert 'Sec-WebSocket-Protocol: sip\r\n' in request
                    nonce=next(line.split(':',1)[1].strip() for line in request.splitlines() if line.startswith('Sec-WebSocket-Key:'))
                    accept=base64.b64encode(hashlib.sha1((nonce+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
                    response=('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                              'Sec-WebSocket-Accept: '+('wrong' if wrong_accept else accept)+'\r\n'
                              'Sec-WebSocket-Protocol: '+('other' if wrong_protocol else 'sip')+'\r\n\r\n').encode()
                    connection.sendall(response[:25]);connection.sendall(response[25:])
            except ssl.SSLError:
                raw.close()
        except BaseException as exc: errors.append(exc)
    worker=threading.Thread(target=serve,daemon=True);worker.start()
    try: yield listener.getsockname()[1]
    finally:
        worker.join(5);listener.close()
        assert not worker.is_alive()
        assert not errors


def test_wss_handshake_verifies_ca_hostname_accept_and_sip_protocol(certificate):
    from lab.wss_probe import probe_wss
    with wss_server(certificate) as port:
        assert probe_wss(certificate[0],port=port) in ('TLSv1.2','TLSv1.3')


@pytest.mark.parametrize('options',[{'wrong_accept':True},{'wrong_protocol':True}])
def test_wss_handshake_rejects_wrong_upgrade_response(certificate,options):
    from lab.wss_probe import probe_wss
    with wss_server(certificate,**options) as port:
        with pytest.raises(ValueError): probe_wss(certificate[0],port=port)


def test_untrusted_ca_is_rejected_and_connection_failure_is_not_acceptance(certificate):
    from lab.wss_probe import untrusted_wss_rejected
    with wss_server(certificate) as port:
        assert untrusted_wss_rejected(port=port) is True
    with pytest.raises(OSError): untrusted_wss_rejected(port=port)
