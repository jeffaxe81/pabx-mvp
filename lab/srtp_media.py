"""Mídia PCMU sintética e SDES-SRTP somente no laboratório loopback."""
import base64
import re
import secrets
import select
import socket
import struct
import time

import pylibsrtp

PROFILE = 'AES_CM_128_HMAC_SHA1_80'
# Um período PCMU de 1 kHz e de 2 kHz, 8 kHz/20 ms: sem voz de pessoas.
TONES = (bytes.fromhex('ff9c8f9cff1c0f1c') * 20,
         bytes.fromhex('ff8fff0f') * 40)


def parse_sdp(body):
    """Recusa downgrade, destinos externos e descrições fora do perfil do lab."""
    if not isinstance(body, bytes) or len(body) > 8192:
        raise ValueError('SDP inválido')
    lines = body.decode('ascii').splitlines()
    connections = [line for line in lines if line.startswith('c=')]
    media = [line for line in lines if line.startswith('m=')]
    cryptos = [line for line in lines if line.startswith('a=crypto:')]
    if (not connections or any(line != 'c=IN IP4 127.0.0.1' for line in connections)
            or len(media) != 1 or len(cryptos) != 1):
        raise ValueError('SDP do laboratório deve ser SRTP loopback')
    match = re.fullmatch(r'm=audio ([0-9]{1,5}) RTP/SAVP ([0-9 ]+)', media[0])
    crypto = re.fullmatch(r'a=crypto:([1-9][0-9]*) '+PROFILE+r' inline:([A-Za-z0-9+/=]+)', cryptos[0])
    if not match or not 1024 <= int(match[1]) <= 65535 or not crypto:
        raise ValueError('perfil SDP não suportado')
    payloads = match[2].split()
    if ('0' not in payloads or len(payloads) != len(set(payloads))
            or any(len(value) > 3 or int(value) > 127 for value in payloads)):
        raise ValueError('codec SDP não suportado')
    if any(line in ('a=sendonly', 'a=recvonly', 'a=inactive') for line in lines):
        raise ValueError('SDP sem mídia bidirecional')
    if any(line.startswith('a=rtpmap:0 ') and line != 'a=rtpmap:0 PCMU/8000' for line in lines):
        raise ValueError('codec SDP inválido')
    try:
        key = base64.b64decode(crypto[2], validate=True)
    except ValueError as exc:
        raise ValueError('chave SDES inválida') from exc
    if len(key) != 30:
        raise ValueError('chave SDES inválida')
    return ('127.0.0.1', int(match[1])), key


def rtp_payload(packet):
    if len(packet) < 12 or packet[0] >> 6 != 2 or packet[1] & 0x7f != 0:
        raise ValueError('pacote PCMU inválido')
    offset = 12 + (packet[0] & 0x0f) * 4
    if len(packet) < offset:
        raise ValueError('cabeçalho RTP incompleto')
    if packet[0] & 0x10:
        if len(packet) < offset + 4:
            raise ValueError('extensão RTP incompleta')
        words = struct.unpack('!H', packet[offset+2:offset+4])[0]
        offset += 4 + 4 * words
    padding = packet[-1] if packet[0] & 0x20 else 0
    if offset > len(packet) or (packet[0] & 0x20 and (padding == 0 or padding > len(packet)-offset)):
        raise ValueError('tamanho RTP inválido')
    return packet[offset:len(packet)-padding if padding else len(packet)]


class SrtpMedia:
    def __init__(self, *, dtmf=False):
        self.dtmf = dtmf
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('127.0.0.1', 0))
        self.socket.setblocking(False)
        self.port = self.socket.getsockname()[1]
        self.key = secrets.token_bytes(30)
        self.crypto_tag = '1'
        self.tx = pylibsrtp.Session(pylibsrtp.Policy(
            key=self.key, ssrc_type=pylibsrtp.Policy.SSRC_ANY_OUTBOUND))
        self.rx = None
        self.address = None
        self.sequence = secrets.randbelow(32000)
        self.timestamp = secrets.randbits(30)
        self.ssrc = secrets.randbits(32)

    def close(self):
        self.socket.close()

    def offer(self):
        return (f'v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\ns=AXE Private Lab\r\n'
                f'c=IN IP4 127.0.0.1\r\nt=0 0\r\nm=audio {self.port} RTP/SAVP {"0 101" if self.dtmf else "0"}\r\n'
                f'a=rtpmap:0 PCMU/8000\r\n'
                + ('a=rtpmap:101 telephone-event/8000\r\na=fmtp:101 0-16\r\n' if self.dtmf else '')
                + f'a=crypto:{self.crypto_tag} {PROFILE} '
                f'inline:{base64.b64encode(self.key).decode()}\r\na=sendrecv\r\n').encode('ascii')

    def negotiate(self, sdp):
        address, key = parse_sdp(sdp)
        if self.dtmf:
            lines = sdp.decode('ascii').splitlines()
            media = [line.split() for line in lines if line.startswith('m=audio ')]
            maps = [line for line in lines if line.startswith('a=rtpmap:101 ')]
            if (len(media) != 1 or '101' not in media[0][3:]
                    or maps != ['a=rtpmap:101 telephone-event/8000']):
                raise ValueError('DTMF RFC4733 não negociado')
        self.crypto_tag = re.search(rb'(?m)^a=crypto:([1-9][0-9]*) ', sdp)[1].decode('ascii')
        self.rx = pylibsrtp.Session(pylibsrtp.Policy(
            key=key, ssrc_type=pylibsrtp.Policy.SSRC_ANY_INBOUND))
        self.address = address

    def protect(self, payload):
        packet = struct.pack('!BBHII', 0x80, 0, self.sequence, self.timestamp, self.ssrc) + payload
        self.sequence = (self.sequence + 1) & 0xffff
        self.timestamp = (self.timestamp + len(payload)) & 0xffffffff
        return self.tx.protect(packet)

    def protect_dtmf(self, digit, *, duration, end=False, marker=False, timestamp=None):
        """Protege evento RFC4733 (PT 101) pelo SRTP do próprio diálogo.

        Não registra dígitos, PIN ou bytes em logs/relatórios. Apenas lab.
        """
        codes = {str(i): i for i in range(10)}
        codes.update({'*': 10, '#': 11, 'A': 12, 'B': 13, 'C': 14, 'D': 15})
        if (not self.dtmf or not isinstance(digit, str) or digit not in codes or type(duration) is not int
                or not 1 <= duration <= 65535):
            raise ValueError('evento DTMF inválido')
        header = struct.pack('!BBHII', 0x80, 101 | (0x80 if marker else 0),
                             self.sequence, self.timestamp if timestamp is None else timestamp,
                             self.ssrc)
        event = struct.pack('!BBH', codes[digit], (0x80 if end else 0) | 10, duration)
        self.sequence = (self.sequence + 1) & 0xffff
        return self.tx.protect(header + event)

    def send_dtmf(self, digit):
        """Envia evento de 140ms e três pacotes de término pela mídia SRTP.

        Não confirma PIN aceito pelo VoiceMailMain; isso requer outro teste.
        """
        if self.address is None or self.rx is None or not self.dtmf:
            raise ValueError('DTMF SRTP não negociado')
        start = self.timestamp
        for index, duration in enumerate((160, 320, 480, 640, 800, 960, 1120, 1120, 1120)):
            packet = self.protect_dtmf(digit, duration=duration,
                                       marker=index == 0, end=index >= 6,
                                       timestamp=start)
            self.socket.sendto(packet, self.address)
            time.sleep(0.02)
        self.timestamp = (start + 1600) & 0xffffffff

    def unprotect(self, packet):
        if self.rx is None:
            raise ValueError('SRTP não negociado')
        return self.rx.unprotect(packet)


def exchange(left, right, *, duration=1.5):
    """Envia tons distintos, valida conteúdo autenticado e testa rejeições locais."""
    peers = (left, right)
    if any(peer.address is None or peer.rx is None for peer in peers):
        raise ValueError('SRTP não negociado')
    received = [0, 0]
    rejection_checked = [False, False]
    deadline = time.monotonic() + duration
    next_send = time.monotonic()
    while time.monotonic() < deadline:
        now = time.monotonic()
        if now >= next_send:
            for i, peer in enumerate(peers):
                peer.socket.sendto(peer.protect(TONES[i]), peer.address)
            next_send = now + 0.02
        ready, _, _ = select.select([p.socket for p in peers], [], [],
                                    max(0, min(next_send, deadline)-time.monotonic()))
        for i, peer in enumerate(peers):
            if peer.socket not in ready:
                continue
            packet, address = peer.socket.recvfrom(4096)
            if address != peer.address:
                raise ValueError('origem de mídia inesperada')
            if not rejection_checked[i]:
                try:
                    peer.unprotect(packet[:-1] + bytes([packet[-1] ^ 1]))
                except pylibsrtp.Error:
                    pass
                else:
                    raise ValueError('SRTP adulterado foi aceito')
            plain = peer.unprotect(packet)
            if rtp_payload(plain) != TONES[1-i]:
                raise ValueError('conteúdo PCMU divergente')
            if not rejection_checked[i]:
                try:
                    peer.unprotect(packet)
                except pylibsrtp.Error:
                    rejection_checked[i] = True
                else:
                    raise ValueError('replay SRTP foi aceito')
            received[i] += 1
    return {'left_received': received[0], 'right_received': received[1],
            'payloads_match': min(received) >= 5, 'authenticated': min(received) >= 5,
            'tamper_rejected': all(rejection_checked), 'replay_rejected': all(rejection_checked)}
