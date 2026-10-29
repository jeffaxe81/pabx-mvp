"""Diálogo SIP/TLS mínimo para chamadas privadas, com prazos e correlação."""
from dataclasses import dataclass
import re
import secrets
import time

from .sip_tls import SipTLS, digest_authorization


def single(headers, name):
    values = headers.get(name, [])
    if len(values) != 1 or any(ch in values[0] for ch in '\r\n'):
        raise ValueError('cabeçalho SIP ausente ou ambíguo')
    return values[0]


def tag(value):
    matches = re.findall(r';tag=([^;\s>]+)', value)
    if len(matches) != 1:
        raise ValueError('tag de diálogo inválida')
    return matches[0]


def contact_uri(headers):
    value = single(headers, 'contact')
    match = re.fullmatch(r'<(sip:(?:[A-Za-z0-9_.-]+@)?127\.0\.0\.1(?::([0-9]{1,5}))?(?:;transport=(?i:tls))?)>', value)
    if not match or not 1 <= int(match[2] or 5061) <= 65535:
        raise ValueError('contato SIP fora do loopback')
    return match[1]


@dataclass
class Dialog:
    call_id: str
    local: str
    remote: str
    uri: str
    cseq: int


class CallRejected(ValueError):
    """Resposta final negativa já correlacionada e confirmada com ACK."""
    def __init__(self, code):
        self.code = code
        super().__init__('chamada SIP rejeitada: '+str(code))


class CallPeer(SipTLS):
    def __init__(self, *args):
        super().__init__(*args)
        self.events = []

    def send_request(self, dialog, method, *, branch=None, body=b'', authorization=None):
        branch = branch or 'z9hG4bK'+secrets.token_hex(12)
        lines = [f'{method} {dialog.uri} SIP/2.0',
                 f'Via: SIP/2.0/TLS 127.0.0.1:{self.port};branch={branch};rport;alias',
                 'Max-Forwards: 70', 'From: '+dialog.local, 'To: '+dialog.remote,
                 'Call-ID: '+dialog.call_id, f'CSeq: {dialog.cseq} {method}',
                 f'Contact: <sip:{self.username}@127.0.0.1:{self.port};transport=tls>',
                 'User-Agent: AXE-Private-Lab']
        if authorization:
            lines.append('Authorization: '+authorization)
        if body:
            lines.append('Content-Type: application/sdp')
        self.connection.sendall(('\r\n'.join(lines)+f'\r\nContent-Length: {len(body)}\r\n\r\n').encode('ascii')+body)
        return branch

    def next_message(self, deadline):
        while True:
            start, headers, body = self.receive(deadline)
            if re.fullmatch(r'(?:NOTIFY|OPTIONS) [^ ]+ SIP/2.0', start):
                self.acknowledge(headers)
                continue
            return start, headers, body

    def final_response(self, dialog, method, branch):
        deadline = time.monotonic() + 10
        while True:
            start, headers, body = self.next_message(deadline)
            match = re.fullmatch(r'SIP/2.0 ([0-9]{3}) .+', start)
            via = headers.get('via', [])
            if (not match or single(headers, 'call-id') != dialog.call_id
                    or single(headers, 'cseq') != f'{dialog.cseq} {method}'
                    or not via or not re.search(r';branch='+re.escape(branch)+r'(?:;|$)', via[0])):
                raise ValueError('resposta de outra transação SIP')
            if tag(single(headers, 'from')) != tag(dialog.local):
                raise ValueError('resposta de outro diálogo SIP')
            self.events.append('response:'+match[1])
            if int(match[1]) >= 200:
                tag(single(headers, 'to'))
                return int(match[1]), headers, body

    def dial(self, number, media):
        if not re.fullmatch(r'(?:\*97|t[1-9][0-9]*-[0-9]{3,6}|[0-9]{3,15})', number):
            raise ValueError('destino do laboratório inválido')
        uri = f'sip:{number}@127.0.0.1:{self.target_port};transport=tls'
        dialog = Dialog(secrets.token_hex(16)+'@localhost',
                        f'<sip:{self.username}@localhost>;tag={secrets.token_hex(8)}',
                        f'<sip:{number}@localhost>', uri, 1)
        branch = self.send_request(dialog, 'INVITE', body=media.offer())
        self.events.append('invite_sent')
        code, headers, _ = self.final_response(dialog, 'INVITE', branch)
        if code != 401:
            raise ValueError('INVITE inicial deve exigir autenticação')
        # ACK de resposta não-2xx pertence à transação original.
        original_remote = dialog.remote
        dialog.remote = single(headers, 'to')
        self.send_request(dialog, 'ACK', branch=branch)
        auth = digest_authorization(single(headers, 'www-authenticate'),
                                    username=self.username, password=self.password,
                                    method='INVITE', uri=uri)
        dialog.remote = original_remote
        dialog.cseq += 1
        branch = self.send_request(dialog, 'INVITE', body=media.offer(), authorization=auth)
        self.events.append('authenticated_invite_sent')
        code, headers, body = self.final_response(dialog, 'INVITE', branch)
        dialog.remote = single(headers, 'to')
        if code != 200:
            self.send_request(dialog, 'ACK', branch=branch)
            raise CallRejected(code)
        tag(dialog.remote)
        dialog.uri = contact_uri(headers)
        self.send_request(dialog, 'ACK')
        self.events.append('ack_sent')
        if single(headers, 'content-type').lower() != 'application/sdp':
            raise ValueError('resposta sem SDP')
        media.negotiate(body)
        return dialog

    def send_response(self, headers, code, *, local, body=b''):
        if not headers.get('via'):
            raise ValueError('requisição sem Via')
        lines = [f'SIP/2.0 {code} Lab', *['Via: '+v for v in headers['via']],
                 'From: '+single(headers, 'from'), 'To: '+local,
                 'Call-ID: '+single(headers, 'call-id'), 'CSeq: '+single(headers, 'cseq'),
                 f'Contact: <sip:{self.username}@127.0.0.1:{self.port};transport=tls>']
        if body:
            lines.append('Content-Type: application/sdp')
        self.connection.sendall(('\r\n'.join(lines)+f'\r\nContent-Length: {len(body)}\r\n\r\n').encode()+body)

    def answer(self, media):
        self.events.append('awaiting_invite')
        deadline = time.monotonic() + 12
        start, headers, body = self.next_message(deadline)
        if not start.startswith('INVITE ') or single(headers, 'content-type').lower() != 'application/sdp':
            raise ValueError('INVITE esperado')
        cseq = re.fullmatch(r'([0-9]+) INVITE', single(headers, 'cseq'))
        if not cseq:
            raise ValueError('CSeq de INVITE inválido')
        self.events.append('invite_received')
        local = single(headers, 'to')+';tag='+secrets.token_hex(8)
        remote = single(headers, 'from')
        tag(remote)
        dialog = Dialog(single(headers, 'call-id'), local, remote, contact_uri(headers), int(cseq[1]))
        media.negotiate(body)
        self.send_response(headers, 180, local=local)
        self.send_response(headers, 200, local=local, body=media.offer())
        self.events.append('answer_sent')
        start, ack, _ = self.next_message(deadline)
        self.validate_incoming(dialog, start, ack, 'ACK')
        if single(ack, 'cseq') != f'{dialog.cseq} ACK':
            raise ValueError('ACK de outra transação SIP')
        self.events.append('ack_received')
        return dialog

    @staticmethod
    def validate_incoming(dialog, start, headers, method):
        if (not start.startswith(method+' ') or single(headers, 'call-id') != dialog.call_id
                or tag(single(headers, 'to')) != tag(dialog.local)
                or tag(single(headers, 'from')) != tag(dialog.remote)):
            raise ValueError('requisição de outro diálogo SIP')

    def hangup(self, dialog):
        dialog.cseq += 1
        branch = self.send_request(dialog, 'BYE')
        self.events.append('bye_sent')
        code, headers, _ = self.final_response(dialog, 'BYE', branch)
        if tag(single(headers, 'to')) != tag(dialog.remote):
            raise ValueError('resposta de outro diálogo SIP')
        return code

    def hangup_or_accept_remote_bye(self, dialog):
        """Encerra após DTMF; aceita BYE remoto SOMENTE se for do mesmo diálogo.

        Asterisk pode encerrar VoiceMailMain ao receber evento de teclado.
        Nenhuma resposta de transação aleatória pode satisfazer este teste.
        """
        dialog.cseq += 1
        branch = self.send_request(dialog, 'BYE')
        self.events.append('bye_sent')
        deadline = time.monotonic() + 10
        while True:
            start, headers, _ = self.next_message(deadline)
            if start.startswith('BYE '):
                self.validate_incoming(dialog, start, headers, 'BYE')
                cseq = re.fullmatch(r'([1-9][0-9]*) BYE', single(headers, 'cseq'))
                if not cseq:
                    raise ValueError('CSeq de BYE remoto inválido')
                self.send_response(headers, 200, local=dialog.local)
                self.events.append('remote_bye_acknowledged')
                return 200
            match = re.fullmatch(r'SIP/2.0 ([0-9]{3}) .+', start)
            via = headers.get('via', [])
            if (not match or single(headers, 'call-id') != dialog.call_id
                    or single(headers, 'cseq') != f'{dialog.cseq} BYE'
                    or not via or not re.search(r';branch='+re.escape(branch)+r'(?:;|$)', via[0])
                    or tag(single(headers, 'from')) != tag(dialog.local)
                    or tag(single(headers, 'to')) != tag(dialog.remote)):
                raise ValueError('resposta de outra transação SIP')
            self.events.append('response:'+match[1])
            if int(match[1]) >= 200:
                return int(match[1])

    def await_hangup(self, dialog):
        start, headers, _ = self.next_message(time.monotonic()+10)
        self.validate_incoming(dialog, start, headers, 'BYE')
        cseq = re.fullmatch(r'([0-9]+) BYE', single(headers, 'cseq'))
        if not cseq or int(cseq[1]) <= dialog.cseq:
            raise ValueError('CSeq de BYE inválido')
        self.send_response(headers, 200, local=dialog.local)
        return True
