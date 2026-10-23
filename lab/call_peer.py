"""Diálogo SIP de laboratório: TLS existente, INVITE/ACK/BYE e SRTP obrigatório."""
import re
import secrets
import time

from .sip_tls import SipTLS, digest_authorization


def one(headers, key):
    values = headers.get(key, [])
    if len(values) != 1:
        raise ValueError('cabeçalho de diálogo SIP ausente ou ambíguo')
    return values[0]


def contact_uri(headers):
    value = one(headers, 'contact')
    match = re.fullmatch(r'<(sip:(?:[A-Za-z0-9_.~-]+@)?127\.0\.0\.1(?::([0-9]+))?(?:;[A-Za-z0-9=_.-]+)*)>', value)
    if not match or (match[2] is not None and not 1 <= int(match[2]) <= 65535):
        raise ValueError('contato SIP não pertence ao laboratório loopback')
    return match[1]


class CallPeer(SipTLS):
    def send_dialog(self, method, uri, *, call_id, from_value, to_value, cseq,
                    branch=None, body=b'', authorization=None):
        if re.search(r'[\r\n ]', uri) or not isinstance(body, bytes):
            raise ValueError('requisição SIP inválida')
        branch = branch or 'z9hG4bK'+secrets.token_hex(12)
        lines = [f'{method} {uri} SIP/2.0',
                 f'Via: SIP/2.0/TLS 127.0.0.1:{self.port};branch={branch};rport;alias',
                 'Max-Forwards: 70', f'From: {from_value}', f'To: {to_value}',
                 f'Call-ID: {call_id}', f'CSeq: {cseq} {method}',
                 f'Contact: <sip:{self.username}@127.0.0.1:{self.port};transport=tls>',
                 'User-Agent: AXE-Private-Call-Lab']
        if authorization:
            lines.append('Authorization: '+authorization)
        if body:
            lines.append('Content-Type: application/sdp')
        lines += [f'Content-Length: {len(body)}', '', '']
        self.connection.sendall('\r\n'.join(lines).encode('ascii')+body)
        return branch

    def reply(self, headers, tag, *, body=b''):
        lines = ['SIP/2.0 200 OK']+['Via: '+v for v in headers.get('via', [])]
        target = one(headers, 'to')
        if not re.search(r';tag=[^;> ]+', target):
            target += ';tag='+tag
        lines += ['From: '+one(headers,'from'), 'To: '+target,
                  'Call-ID: '+one(headers,'call-id'), 'CSeq: '+one(headers,'cseq'),
                  f'Contact: <sip:{self.username}@127.0.0.1:{self.port};transport=tls>']
        if body:
            lines.append('Content-Type: application/sdp')
        lines += [f'Content-Length: {len(body)}', '', '']
        self.connection.sendall('\r\n'.join(lines).encode('ascii')+body)
        return target

    def next_message(self, deadline):
        while True:
            start, headers, body = self.receive(deadline)
            if re.fullmatch(r'(?:NOTIFY|OPTIONS) [^ ]+ SIP/2.0', start):
                self.acknowledge(headers)
                continue
            return start, headers, body

    def response(self, call_id, cseq, method):
        deadline = time.monotonic()+8
        while True:
            start, headers, body = self.next_message(deadline)
            if (one(headers,'call-id') != call_id or one(headers,'cseq') != f'{cseq} {method}'):
                raise ValueError('resposta não corresponde ao diálogo da chamada')
            match = re.fullmatch(r'SIP/2.0 ([0-9]{3}) .+', start)
            if not match:
                raise ValueError('resposta da chamada inválida')
            code = int(match[1])
            if code >= 200:
                return code, headers, body

    def invite(self, number, media):
        if not re.fullmatch(r'120[12]', number):
            raise ValueError('destino fora do conjunto de teste')
        uri = f'sip:{number}@localhost:{self.target_port};transport=tls'
        call_id = secrets.token_hex(16)+'@localhost'
        local = f'<sip:{self.username}@localhost>;tag='+secrets.token_hex(8)
        remote = f'<sip:{number}@localhost>'
        seq = 1
        branch = self.send_dialog('INVITE',uri,call_id=call_id,from_value=local,
                                  to_value=remote,cseq=seq,body=media.offer())
        code, headers, body = self.response(call_id,seq,'INVITE')
        if code == 401:
            # ACK da resposta negativa usa a mesma transação Via/CSeq.
            self.send_dialog('ACK',uri,call_id=call_id,from_value=local,
                             to_value=one(headers,'to'),cseq=seq,branch=branch)
            auth = digest_authorization(one(headers,'www-authenticate'), username=self.username,
                                        password=self.password,method='INVITE',uri=uri)
            seq += 1
            self.send_dialog('INVITE',uri,call_id=call_id,from_value=local,
                             to_value=remote,cseq=seq,body=media.offer(),authorization=auth)
            code, headers, body = self.response(call_id,seq,'INVITE')
        if code != 200 or one(headers,'content-type').split(';')[0].lower() != 'application/sdp':
            raise ValueError('chamada não estabelecida com SDP')
        media.negotiate(body)
        if media.remote.tag != '1':
            raise ValueError('resposta não selecionou a oferta SDES')
        self.dialog = {'call_id':call_id,'local':local,'remote':one(headers,'to'),
                       'uri':contact_uri(headers),'cseq':seq}
        self.send_dialog('ACK',self.dialog['uri'],call_id=call_id,from_value=local,
                         to_value=self.dialog['remote'],cseq=seq)
        return True

    def answer(self, media):
        start, headers, body = self.next_message(time.monotonic()+10)
        if not re.match(r'^INVITE sip:'+re.escape(self.username)+r'@',start):
            raise ValueError('INVITE não foi destinado ao ramal esperado')
        if not re.fullmatch(r'[0-9]+ INVITE',one(headers,'cseq')):
            raise ValueError('CSeq INVITE inválido')
        if one(headers,'content-type').split(';')[0].lower() != 'application/sdp':
            raise ValueError('INVITE sem SDP')
        media.negotiate(body)
        tag = secrets.token_hex(8)
        local = self.reply(headers,tag,body=media.offer(media.remote.tag))
        self.dialog = {'call_id':one(headers,'call-id'),'local':local,
                       'remote':one(headers,'from'),'cseq':int(one(headers,'cseq').split()[0])}
        return True

    def hangup(self):
        dialog = self.dialog
        seq = dialog['cseq']+1
        self.send_dialog('BYE',dialog['uri'],call_id=dialog['call_id'],
                         from_value=dialog['local'],to_value=dialog['remote'],cseq=seq)
        code, headers, _ = self.response(dialog['call_id'],seq,'BYE')
        if code == 401:
            auth = digest_authorization(one(headers,'www-authenticate'), username=self.username,
                                        password=self.password,method='BYE',uri=dialog['uri'])
            seq += 1
            self.send_dialog('BYE',dialog['uri'],call_id=dialog['call_id'],from_value=dialog['local'],
                             to_value=dialog['remote'],cseq=seq,authorization=auth)
            code, _, _ = self.response(dialog['call_id'],seq,'BYE')
        return code == 200

    def wait_for_bye(self):
        deadline = time.monotonic()+10
        ack = False
        while True:
            start, headers, _ = self.next_message(deadline)
            if one(headers,'call-id') != self.dialog['call_id']:
                raise ValueError('requisição pertence a outra chamada')
            if one(headers,'from') != self.dialog['remote'] or one(headers,'to') != self.dialog['local']:
                raise ValueError('tags não correspondem ao diálogo')
            if start.startswith('ACK ') and one(headers,'cseq') == f'{self.dialog["cseq"]} ACK':
                ack = True
            elif start.startswith('BYE '):
                match = re.fullmatch(r'([0-9]+) BYE',one(headers,'cseq'))
                if not match or int(match[1]) <= self.dialog['cseq']:
                    raise ValueError('CSeq BYE inválido')
                self.reply(headers,'unused')
                return ack
            else:
                raise ValueError('requisição não prevista durante chamada de teste')
