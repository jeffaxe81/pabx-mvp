"""Private voicemail experiment helpers; never return PINs, SDP or raw logs.

Prompt evidence proves application state and requested message playback, not
audible media content. Pair it with authenticated SRTP marker observation for
message-content acceptance. Only use an owned, disposable Asterisk container.
"""
import re
import struct
import time

from .srtp_media import SrtpMedia


def inspect_auth_prompts(raw, channel, tenant):
    """Inspect only exact-channel playback records, discarding all other logs.

    Asterisk verbose level 3 logs incorrect PINs verbatim. This function must
    receive those logs privately; its return value contains no text from them.
    """
    if (not isinstance(raw, str) or len(raw) > 2 * 1024 * 1024
            or not isinstance(channel, str) or not isinstance(tenant, str)
            or re.fullmatch(r't[1-9][0-9]*', tenant) is None):
        raise ValueError('escopo voicemail inválido')
    match = re.fullmatch(r'PJSIP/(' + re.escape(tenant)
                         + r'-[a-z0-9][a-z0-9_-]*)-[0-9a-f]+', channel)
    if match is None:
        raise ValueError('escopo voicemail inválido')
    mailbox = match[1]
    result = {'password_prompts': 0, 'incorrect_prompts': 0,
              'authenticated_intro': False, 'goodbye': False,
              'own_message': False, 'foreign_message': False}
    pattern = re.compile(r'<' + re.escape(channel) + r"> Playing '([^'\r\n]+)'(?: |$)")
    for line in raw.splitlines():
        record = pattern.search(line)
        if record is None:
            continue
        path = record[1]
        prompt = re.sub(r'\.(?:slin|slin16|ulaw|alaw|gsm|wav|g722)$', '', path)
        if prompt == 'vm-password':
            result['password_prompts'] += 1
        elif prompt in ('vm-incorrect', 'vm-incorrect-mailbox'):
            result['incorrect_prompts'] += 1
        elif prompt in ('vm-youhave', 'vm-youhaveno', 'vm-opts'):
            result['authenticated_intro'] = True
        elif prompt == 'vm-goodbye':
            result['goodbye'] = True
        elif '/voicemail/' in path:
            own = re.fullmatch(
                r'/var/spool/asterisk/voicemail/' + re.escape(tenant) + '/'
                + re.escape(mailbox) + r'/(?:INBOX|Old|Urgent)/msg[0-9]{4}'
                r'(?:\.(?:wav|WAV|gsm|ulaw|slin))?', path) is not None
            result['own_message' if own else 'foreign_message'] = True
    return result


class VoicemailMedia(SrtpMedia):
    """PCMU plus RFC4733 DTMF, encrypted using the same SRTP session."""

    def offer(self):
        return (super().offer().replace(b'RTP/SAVP 0\r\n', b'RTP/SAVP 0 101\r\n')
                + b'a=rtpmap:101 telephone-event/8000\r\na=fmtp:101 0-16\r\n')

    def negotiate(self, sdp):
        if not isinstance(sdp, bytes) or len(sdp) > 8192:
            raise ValueError('SDP DTMF inválido')
        lines = sdp.splitlines()
        mappings = [line for line in lines if line.startswith(b'a=rtpmap:101 ')]
        media = [line.split() for line in lines if line.startswith(b'm=audio ')]
        if (mappings != [b'a=rtpmap:101 telephone-event/8000'] or len(media) != 1
                or b'101' not in media[0][3:]):
            raise ValueError('negociação DTMF indisponível')
        super().negotiate(sdp)

    def protect_event(self, digit, *, duration, end=False, marker=False):
        digits = '0123456789*#ABCD'
        if (not isinstance(digit, str) or len(digit) != 1 or digit not in digits
                or type(duration) is not int or not 1 <= duration <= 65535):
            raise ValueError('evento DTMF inválido')
        packet = struct.pack('!BBHII', 0x80, 101 | (0x80 if marker else 0),
                             self.sequence, self.timestamp, self.ssrc)
        packet += struct.pack('!BBH', digits.index(digit), 10 | (0x80 if end else 0), duration)
        self.sequence = (self.sequence + 1) & 0xffff
        return self.tx.protect(packet)

    def send_digits(self, digits):
        """Send bounded private digits, 160 ms each plus redundant end packets.

        The caller must first wait for the corresponding live password/menu
        prompt. Do not include this argument in reports or exception messages.
        """
        if (not isinstance(digits, str) or not 1 <= len(digits) <= 32
                or any(d not in '0123456789*#ABCD' for d in digits)):
            raise ValueError('sequência DTMF inválida')
        if self.address is None or self.rx is None:
            raise ValueError('SRTP não negociado')
        for digit in digits:
            for duration in range(160, 1281, 160):
                self.socket.sendto(self.protect_event(
                    digit, duration=duration, marker=duration == 160), self.address)
                time.sleep(0.02)
            for _ in range(3):
                self.socket.sendto(self.protect_event(
                    digit, duration=1280, end=True), self.address)
                time.sleep(0.02)
            self.timestamp = (self.timestamp + 2080) & 0xffffffff
            time.sleep(0.04)
