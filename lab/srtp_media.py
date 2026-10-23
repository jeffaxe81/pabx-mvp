"""Mídia de teste PCMU/SDES-SRTP em loopback, sem exportar chaves ou áudio."""
import base64
from dataclasses import dataclass, field
import re
import secrets
import select
import socket
import struct
import time

from pylibsrtp import Error, Policy, Session


@dataclass(frozen=True)
class Sdes:
    address: tuple
    tag: str
    key: bytes = field(repr=False)


def parse_sdes(body):
    if not isinstance(body, bytes) or len(body) > 8192:
        raise ValueError('SDP inválido ou excessivo')
    try:
        lines = body.decode('ascii').replace('\r\n', '\n').splitlines()
    except UnicodeError:
        raise ValueError('SDP deve ser ASCII') from None
    media = [line for line in lines if line.startswith('m=')]
    connections = [line for line in lines if line.startswith('c=')]
    if len(media) != 1 or len(connections) != 1 or connections[0] != 'c=IN IP4 127.0.0.1':
        raise ValueError('SDP requer uma mídia e destino loopback único')
    match = re.fullmatch(r'm=audio ([0-9]+) RTP/SAVP ([0-9 ]+)', media[0])
    if not match or not 1 <= int(match[1]) <= 65535 or '0' not in match[2].split():
        raise ValueError('SDP requer PCMU e RTP/SAVP')
    if any(line in ('a=inactive','a=sendonly','a=recvonly') for line in lines):
        raise ValueError('SDP deve permitir mídia bidirecional')
    crypto = [re.fullmatch(r'a=crypto:([1-9][0-9]*) AES_CM_128_HMAC_SHA1_80 inline:([A-Za-z0-9+/=]+)', line)
              for line in lines if line.startswith('a=crypto:')]
    crypto = [item for item in crypto if item]
    if len(crypto) != 1:
        raise ValueError('SDP requer uma chave SDES SHA1-80 válida')
    try:
        key = base64.b64decode(crypto[0][2], validate=True)
    except ValueError:
        raise ValueError('chave SDES inválida') from None
    if len(key) != 30:
        raise ValueError('SDES requer chave e salt de 30 bytes')
    return Sdes(('127.0.0.1', int(match[1])), crypto[0][1], key)


def rtp_payload(packet):
    if len(packet) < 12 or packet[0] >> 6 != 2 or packet[1] & 0x7f != 0:
        raise ValueError('RTP não é PCMU válido')
    offset = 12 + 4*(packet[0] & 15)
    if len(packet) < offset:
        raise ValueError('RTP truncado')
    if packet[0] & 0x10:
        if len(packet) < offset+4:
            raise ValueError('extensão RTP truncada')
        offset += 4 + 4*struct.unpack_from('!H', packet, offset+2)[0]
    end = len(packet)
    if packet[0] & 0x20:
        if not packet[-1] or packet[-1] > len(packet)-offset:
            raise ValueError('padding RTP inválido')
        end -= packet[-1]
    if offset > end:
        raise ValueError('RTP truncado')
    return packet[offset:end]


class SrtpMedia:
    def __init__(self, payload):
        if not isinstance(payload, bytes) or len(payload) != 160:
            raise ValueError('PCMU de teste deve conter 160 amostras')
        self.payload = payload
        self.key = secrets.token_bytes(30)
        self.tx = Session(Policy(key=self.key, ssrc_type=Policy.SSRC_ANY_OUTBOUND))
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('127.0.0.1', 0))
        self.socket.setblocking(False)
        self.remote = None
        self.rx = None
        self.ssrc = int.from_bytes(secrets.token_bytes(4), 'big')

    def offer(self, tag='1'):
        if not re.fullmatch(r'[1-9][0-9]*', tag):
            raise ValueError('tag SDES inválida')
        key = base64.b64encode(self.key).decode('ascii')
        port = self.socket.getsockname()[1]
        return (f'v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\ns=AXE private lab\r\n'
                f'c=IN IP4 127.0.0.1\r\nt=0 0\r\nm=audio {port} RTP/SAVP 0\r\n'
                f'a=crypto:{tag} AES_CM_128_HMAC_SHA1_80 inline:{key}\r\n'
                'a=rtpmap:0 PCMU/8000\r\na=ptime:20\r\na=sendrecv\r\n').encode('ascii')

    def negotiate(self, body):
        self.remote = parse_sdes(body)
        self.rx = Session(Policy(key=self.remote.key, ssrc_type=Policy.SSRC_ANY_INBOUND))

    def exchange(self, expected_payload, barrier=None, *, packets=80):
        if self.remote is None or self.rx is None or type(packets) is not int or not 5 <= packets <= 200:
            raise ValueError('mídia não negociada ou quantidade de pacotes inválida')
        if not isinstance(expected_payload, bytes) or len(expected_payload) != 160:
            raise ValueError('áudio esperado inválido')
        if barrier is not None:
            barrier.wait(timeout=5)
        stats = {'sent':0, 'received_expected':0, 'received_other':0,
                 'encrypted_wire':False, 'wrong_key_rejected':False, 'success':False}
        wrong = Session(Policy(key=secrets.token_bytes(30), ssrc_type=Policy.SSRC_ANY_INBOUND))
        started = time.monotonic()
        deadline = started + packets*0.02 + 1.0
        sent_encrypted = True
        received_encrypted = False
        while time.monotonic() < deadline:
            now = time.monotonic()
            if stats['sent'] < packets and now >= started+stats['sent']*0.02:
                seq = stats['sent']
                raw = struct.pack('!BBHII', 0x80, 0, seq, seq*160, self.ssrc)+self.payload
                protected = self.tx.protect(raw)
                sent_encrypted &= len(protected) == len(raw)+10 and protected[12:172] != self.payload
                self.socket.sendto(protected, self.remote.address)
                stats['sent'] += 1
            ready, _, _ = select.select([self.socket], [], [], 0.005)
            if not ready:
                continue
            packet, address = self.socket.recvfrom(4096)
            if address != self.remote.address:
                continue
            try:
                clear = self.rx.unprotect(packet)
                payload = rtp_payload(clear)
            except (Error, ValueError):
                continue
            if payload == expected_payload:
                stats['received_expected'] += 1
                received_encrypted |= packet[12:172] != payload and len(packet) == len(clear)+10
            else:
                stats['received_other'] += 1
            if not stats['wrong_key_rejected']:
                try:
                    wrong.unprotect(packet)
                except Error:
                    stats['wrong_key_rejected'] = True
        stats['encrypted_wire'] = bool(sent_encrypted and received_encrypted)
        stats['success'] = (stats['sent'] == packets and stats['received_expected'] >= 20
                            and stats['received_other'] == 0 and stats['encrypted_wire']
                            and stats['wrong_key_rejected'])
        return stats

    def close(self):
        self.socket.close()
