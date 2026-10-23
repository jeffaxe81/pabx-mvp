"""Cliente SIP mínimo para o laboratório loopback; sem logs de credenciais."""
import hashlib
import re
import secrets
import socket
import ssl
import time
from urllib.request import parse_http_list, parse_keqv_list

LIMIT = 65536


def pop_message(buffer):
    """Extrai uma mensagem do fluxo TLS, preservando fragmentos e mensagens extras."""
    if len(buffer) > LIMIT:
        raise ValueError('mensagem SIP excessiva')
    boundary = buffer.find(b'\r\n\r\n')
    if boundary < 0:
        return None, buffer
    header = buffer[:boundary].decode('ascii')
    lengths = re.findall(r'(?im)^Content-Length\s*:\s*([^\r\n]+)', header)
    if len(lengths) != 1 or not lengths[0].isdigit():
        raise ValueError('Content-Length SIP inválido')
    length = int(lengths[0])
    end = boundary + 4 + length
    if end > LIMIT:
        raise ValueError('corpo SIP excessivo')
    if len(buffer) < end:
        return None, buffer
    return buffer[:end], buffer[end:]


def digest_authorization(challenge, *, username, password, method, uri, cnonce=None):
    if not challenge.startswith('Digest '):
        raise ValueError('desafio Digest ausente')
    fields = parse_keqv_list(parse_http_list(challenge[7:]))
    algorithm = fields.get('algorithm', 'MD5').upper()
    if algorithm not in ('MD5', 'SHA-256') or not fields.get('realm') or not fields.get('nonce'):
        raise ValueError('desafio Digest não suportado')
    qops = [v.strip() for v in fields.get('qop', '').split(',') if v.strip()]
    if qops and 'auth' not in qops:
        raise ValueError('qop Digest não suportado')
    for value in (username, fields['realm'], fields['nonce'], uri, fields.get('opaque', '')):
        if any(ch in value for ch in '\r\n"\\'):
            raise ValueError('valor Digest inseguro')
    def h(value):
        return hashlib.new(algorithm.lower().replace('-', ''), value.encode()).hexdigest()
    ha1 = h(f"{username}:{fields['realm']}:{password}")
    ha2 = h(f'{method}:{uri}')
    cnonce = cnonce or secrets.token_hex(16)
    response = h(f"{ha1}:{fields['nonce']}:00000001:{cnonce}:auth:{ha2}") if qops else h(
        f"{ha1}:{fields['nonce']}:{ha2}")
    result = (f'Digest username="{username}", realm="{fields["realm"]}", '
              f'nonce="{fields["nonce"]}", uri="{uri}", response="{response}", algorithm={algorithm}')
    if qops:
        result += f', qop=auth, nc=00000001, cnonce="{cnonce}"'
    if 'opaque' in fields:
        result += f', opaque="{fields["opaque"]}"'
    return result


def parse_message(raw):
    headers, body = raw.split(b'\r\n\r\n', 1)
    lines = headers.decode('ascii').split('\r\n')
    values = {}
    for line in lines[1:]:
        key, separator, value = line.partition(':')
        if not separator:
            raise ValueError('cabeçalho SIP inválido')
        values.setdefault(key.lower(), []).append(value.strip())
    return lines[0], values, body


class SipTLS:
    def __init__(self, host, port, ca_file, username, password):
        if host != '127.0.0.1':
            raise ValueError('laboratório permite somente loopback IPv4')
        if not re.fullmatch(r't[1-9][0-9]*-[A-Za-z0-9-]+', username):
            raise ValueError('usuário de laboratório inválido')
        self.username, self.password = username, password
        self.context = ssl.create_default_context(cafile=str(ca_file))
        self.context.minimum_version = ssl.TLSVersion.TLSv1_2
        raw = socket.create_connection((host, port), timeout=5)
        try:
            self.connection = self.context.wrap_socket(raw, server_hostname='localhost')
        except BaseException:
            raw.close()
            raise
        self.connection.settimeout(5)
        self.port = self.connection.getsockname()[1]
        self.target_port = port
        self.buffer = b''
        self.call_id = secrets.token_hex(16) + '@localhost'
        self.tag = secrets.token_hex(8)
        self.cseq = 0

    def close(self):
        self.connection.close()

    def receive(self):
        while True:
            # SIP keepalive CRLF não constitui uma mensagem.
            self.buffer = self.buffer.lstrip(b'\r\n')
            message, self.buffer = pop_message(self.buffer)
            if message is not None:
                return parse_message(message)
            data = self.connection.recv(8192)
            if not data:
                raise ConnectionError('conexão SIP encerrada')
            self.buffer += data

    def request(self, method, uri, *, authorization=None, expires=120):
        self.cseq += 1
        branch = 'z9hG4bK' + secrets.token_hex(12)
        lines = [f'{method} {uri} SIP/2.0',
                 f'Via: SIP/2.0/TLS 127.0.0.1:{self.port};branch={branch};rport;alias',
                 'Max-Forwards: 70',
                 f'From: <sip:{self.username}@localhost>;tag={self.tag}',
                 f'To: <sip:{self.username}@localhost>',
                 f'Call-ID: {self.call_id}', f'CSeq: {self.cseq} {method}',
                 f'Contact: <sip:{self.username}@127.0.0.1:{self.port};transport=tls>',
                 f'Expires: {expires}', 'User-Agent: AXE-Private-Lab']
        if authorization:
            lines.append('Authorization: ' + authorization)
        lines += ['Content-Length: 0', '', '']
        self.connection.sendall('\r\n'.join(lines).encode('ascii'))
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            start, headers, body = self.receive()
            if (headers.get('call-id') != [self.call_id] or
                    headers.get('cseq') != [f'{self.cseq} {method}']):
                raise ValueError('resposta de outra transação SIP')
            match = re.fullmatch(r'SIP/2.0 ([0-9]{3}) .+', start)
            if not match:
                raise ValueError('resposta SIP inválida')
            status = int(match[1])
            if status >= 200:
                return status, headers
        raise TimeoutError('transação SIP sem resposta final')

    def register(self, *, expires=120):
        uri = f'sip:localhost:{self.target_port};transport=tls'
        code, headers = self.request('REGISTER', uri, expires=expires)
        if code != 401:
            raise ValueError('REGISTER inicial deve exigir autenticação')
        challenges = headers.get('www-authenticate', [])
        if len(challenges) != 1:
            raise ValueError('desafio REGISTER ausente ou ambíguo')
        auth = digest_authorization(challenges[0], username=self.username,
                                    password=self.password, method='REGISTER', uri=uri)
        final, _ = self.request('REGISTER', uri, authorization=auth, expires=expires)
        return final
