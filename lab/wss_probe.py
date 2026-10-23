"""Verifica CA, hostname e upgrade SIP/WSS sem divulgar mensagens ou chaves."""
import base64
import hashlib
import secrets
import socket
import ssl


def probe_wss(cafile, *, port=8089):
    context=ssl.create_default_context(cafile=str(cafile))
    context.minimum_version=ssl.TLSVersion.TLSv1_2
    nonce=base64.b64encode(secrets.token_bytes(16)).decode('ascii')
    with socket.create_connection(('127.0.0.1',port),timeout=5) as raw:
        with context.wrap_socket(raw,server_hostname='localhost') as connection:
            connection.sendall((f'GET /ws HTTP/1.1\r\nHost: localhost:{port}\r\n'
                'Upgrade: websocket\r\nConnection: Upgrade\r\n'
                f'Sec-WebSocket-Key: {nonce}\r\nSec-WebSocket-Version: 13\r\n'
                'Sec-WebSocket-Protocol: sip\r\n\r\n').encode('ascii'))
            data=b''
            while b'\r\n\r\n' not in data:
                chunk=connection.recv(4096)
                if not chunk or len(data)+len(chunk)>16384: raise ValueError('upgrade WSS incompleto')
                data+=chunk
            lines=data.split(b'\r\n\r\n',1)[0].decode('ascii').split('\r\n')
            headers={}
            for line in lines[1:]:
                name,separator,value=line.partition(':')
                if not separator or name.lower() in headers: raise ValueError('upgrade WSS ambíguo')
                headers[name.lower()]=value.strip()
            expected=base64.b64encode(hashlib.sha1((nonce+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
            if (not lines[0].startswith('HTTP/1.1 101 ') or headers.get('upgrade','').lower()!='websocket'
                    or 'upgrade' not in [token.strip().lower() for token in headers.get('connection','').split(',')]
                    or headers.get('sec-websocket-accept')!=expected or headers.get('sec-websocket-protocol')!='sip'):
                raise ValueError('upgrade WSS inválido')
            return connection.version()


def untrusted_wss_rejected(*, port=8089):
    context=ssl.create_default_context()
    context.minimum_version=ssl.TLSVersion.TLSv1_2
    try:
        with socket.create_connection(('127.0.0.1',port),timeout=5) as raw:
            with context.wrap_socket(raw,server_hostname='localhost'):
                return False
    except ssl.SSLCertVerificationError:
        return True
