"""Real voicemail authentication and synthetic message isolation on loopback.

All PINs, logs and audio remain private to the disposable lab. Reports contain
only booleans; the production *97 dialplan and mailbox authentication stay intact.
"""
from contextlib import ExitStack
import math
import re
import secrets
import select
import struct
import time
import wave

from .sip_calls import CallPeer
from .srtp_media import rtp_payload
from .voicemail_auth_checks import VoicemailMedia, inspect_auth_prompts

TENANTS = ('t1', 't10')
METRICS = ('registered', 'correct_pin', 'own_message', 'srtp_marker',
           'no_foreign_message', 'foreign_pin_denied', 'max_attempts', 'channels_cleared')
LOG_PATH = '/var/log/asterisk/voicemail-auth'


def required_voicemail_auth_checks():
    return {'vm_auth_'+name+':'+tenant for tenant in TENANTS for name in METRICS}


def tone_flags(payload):
    """Recognize pure 1/2 kHz synthetic markers, returning no audio samples."""
    if not isinstance(payload, bytes) or not 80 <= len(payload) <= 800:
        return False, False
    samples = []
    for value in payload:
        value = ~value & 255
        sample = (((value & 15) << 3) + 132) << ((value & 112) >> 4)
        sample -= 132
        samples.append(-sample if value & 128 else sample)
    energy = sum(x*x for x in samples)
    if energy < len(samples)*10000:
        return False, False
    result = []
    for frequency in (1000, 2000):
        real = sum(x*math.cos(2*math.pi*frequency*i/8000) for i, x in enumerate(samples))
        imag = sum(x*math.sin(2*math.pi*frequency*i/8000) for i, x in enumerate(samples))
        result.append(2*(real*real + imag*imag)/(len(samples)*energy) > .92)
    return tuple(result)


def prepare_voicemail_auth(root, prepared, source):
    """Extend only the already-private staging, after the base PIN preflight."""
    from .asterisk_lab import command, load_file
    conf = prepared['conf']
    tenants = load_file('lab_vm_auth_tenants', conf.parent/'helpers/tenants.py')
    generator_path = conf.parent/'helpers/voicemail_conf_generator.py'
    generator_path.write_text(command(['git', '-C', str(root), 'show',
                                      source+':admin-api/conf_generator.py']).stdout)
    generator_path.chmod(0o600)
    generator = load_file('lab_vm_auth_generator', generator_path)
    credentials = tenants.generate_tenant_credentials('t10')
    prepared['credentials'].update(credentials)
    for folder, body in (
        ('pjsip_tenants', tenants.render_tenant_pjsip('t10', credentials)),
        ('extensions_tenants', tenants.render_tenant_extensions('t10')),
        ('queues_tenants', tenants.render_tenant_queues('t10')),
        ('voicemail_tenants', tenants.render_tenant_voicemail('t10')),
        ('parking_tenants', tenants.render_tenant_parking('t10')),
    ):
        path = conf/folder/'t10.conf'
        path.write_text(body)
        path.chmod(0o600)
    static_vm = (conf/'voicemail.conf').read_text()
    matches = re.findall(r'(?m)^t1-1001\s*=>\s*([1-9][0-9]{7}),', static_vm)
    if len(matches) != 1:
        raise ValueError('PIN privado de laboratório ausente ou ambíguo')
    pin = matches[0]
    other_pin = pin
    while other_pin == pin:
        other_pin = str(secrets.randbelow(90000000)+10000000)
    password = secrets.token_urlsafe(32)
    prepared['credentials']['t10-1001'] = password
    extension = {'name': 't10-1001', 'number': '1001', 'tenant': 't10',
                 'password': password, 'display_name': 'Private Voicemail Lab',
                 'voicemail_pin': other_pin}
    for filename, body in generator.render_all([extension], tenant_ids=('t10',)).items():
        path = conf/'generated'/filename
        with path.open('a') as output:
            output.write('\n'+body)
        path.chmod(0o600)
    prepared['voicemail_auth_pins'] = {'t1': pin, 't10': other_pin}
    seed = conf.parent/'voicemail_auth_seed'
    for tenant, frequency in zip(TENANTS, (1000, 2000)):
        inbox = seed/tenant/(tenant+'-1001')/'INBOX'
        inbox.mkdir(mode=0o700, parents=True)
        with wave.open(str(inbox/'msg0000.wav'), 'wb') as audio:
            audio.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
            audio.writeframes(b''.join(struct.pack('<h', round(8000*math.sin(
                2*math.pi*frequency*i/8000))) for i in range(24000)))
        (inbox/'msg0000.txt').write_text(
            '[message]\norigmailbox='+tenant+'-1001\ncontext='+tenant+'-internal\n'
            'exten=1001\npriority=1\ncallerchan=Local/private-lab\n'
            'callerid=Private Lab <1001>\norigdate=Thu Oct 1 12:00:00 UTC 2026\n'
            'origtime=1790856000\nduration=3\nmsg_id=1790856000-00000001\nflag=\n')
    for path in seed.rglob('*'):
        path.chmod(0o700 if path.is_dir() else 0o600)
    prepared['voicemail_auth_seed'] = seed
    # Incorrect PINs appear in verbose messages: only the private file gets them.
    with (conf/'logger.conf').open('a') as output:
        output.write('\nvoicemail-auth => verbose\n')


class _Observer:
    def __init__(self, media):
        self.media = media
        self.markers = [0, 0]
        self.authenticated_packets = 0

    def pump(self, duration=.1):
        deadline = time.monotonic()+duration
        next_send = time.monotonic()
        while time.monotonic() < deadline:
            now = time.monotonic()
            if now >= next_send:
                self.media.socket.sendto(self.media.protect(b'\xff'*160), self.media.address)
                next_send = now+.02
            ready, _, _ = select.select([self.media.socket], [], [],
                                        max(0, min(deadline, next_send)-time.monotonic()))
            if ready:
                packet, address = self.media.socket.recvfrom(4096)
                if address != self.media.address:
                    raise ValueError('origem SRTP voicemail inesperada')
                plain = self.media.unprotect(packet)
                if plain[1] & 127 != 0:
                    continue
                flags = tone_flags(rtp_payload(plain))
                self.authenticated_packets += 1
                for index, flag in enumerate(flags):
                    self.markers[index] += int(flag)


def exercise_voicemail_auth(container, prepared, report):
    from .asterisk_lab import cli, command
    checks = report['checks']
    checks.update({key: False for key in required_voicemail_auth_checks()})
    report['live_voicemail_auth_tested'] = False
    report['voicemail_auth_cases'] = {}
    command(['docker', 'exec', container, 'mkdir', '-p', '/var/spool/asterisk/voicemail'])
    command(['docker', 'cp', str(prepared['voicemail_auth_seed'])+'/.',
             container+':/var/spool/asterisk/voicemail/'])
    cli(container, 'logger reload')
    cli(container, 'core set verbose 3')

    def logs(channel, tenant):
        result = command(['docker', 'exec', container, 'cat', LOG_PATH], check=False)
        return inspect_auth_prompts(result.stdout if result.returncode == 0 else '', channel, tenant)

    def channel_for(endpoint):
        deadline = time.monotonic()+5
        while time.monotonic() < deadline:
            matches = [line.split('!', 1)[0] for line in cli(container, 'core show channels concise').splitlines()
                       if re.match(r'PJSIP/'+re.escape(endpoint)+r'-[0-9a-f]+!', line)]
            if len(matches) == 1:
                return matches[0]
            time.sleep(.1)
        raise ValueError('canal voicemail não identificado inequivocamente')

    def wait(observer, channel, tenant, predicate, timeout=15):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            observer.pump(.12)
            result = logs(channel, tenant)
            if predicate(result):
                return result
        raise ValueError('estado esperado do voicemail não observado')

    for index, tenant in enumerate(TENANTS):
        endpoint = tenant+'-1001'
        own_index, foreign_index = index, 1-index
        values = {metric: False for metric in METRICS}
        for positive in (True, False):
            report['phase'] = 'voicemail-auth:'+tenant+(':positive' if positive else ':foreign-pin')
            with ExitStack() as resources:
                peer = CallPeer('127.0.0.1', 5061, prepared['ca'], endpoint,
                                prepared['credentials'][endpoint])
                resources.callback(peer.close)
                media = VoicemailMedia()
                resources.callback(media.close)
                registered = peer.register() == 200
                if not registered:
                    raise ValueError('registro de voicemail rejeitado')
                values['registered'] = registered
                dialog = peer.dial('*97', media)
                channel = channel_for(endpoint)
                observer = _Observer(media)
                wait(observer, channel, tenant, lambda state: state['password_prompts'] == 1)
                if positive:
                    media.send_digits(prepared['voicemail_auth_pins'][tenant]+'#')
                    result = wait(observer, channel, tenant, lambda state: state['authenticated_intro'])
                    values['correct_pin'] = result['incorrect_prompts'] == 0
                    observer.markers = [0, 0]
                    media.send_digits('1')
                    result = wait(observer, channel, tenant, lambda state: state['own_message']
                                  and observer.markers[own_index] >= 5, timeout=35)
                    # Observe the complete synthetic playback, not only its first packets.
                    observer.pump(3.5)
                    result = logs(channel, tenant)
                    values['own_message'] = result['own_message']
                    values['srtp_marker'] = observer.markers[own_index] >= 5
                    values['no_foreign_message'] = (not result['foreign_message']
                                                    and observer.markers[foreign_index] == 0)
                    if peer.hangup(dialog) != 200:
                        raise ValueError('desligamento voicemail não confirmado')
                else:
                    foreign_tenant = TENANTS[foreign_index]
                    for attempt in range(1, 4):
                        media.send_digits(prepared['voicemail_auth_pins'][foreign_tenant]+'#')
                        result = wait(observer, channel, tenant,
                                      lambda state: state['incorrect_prompts'] >= attempt)
                        if attempt < 3:
                            wait(observer, channel, tenant,
                                 lambda state: state['password_prompts'] == attempt+1)
                    result = wait(observer, channel, tenant, lambda state: state['goodbye'])
                    values['foreign_pin_denied'] = (not result['authenticated_intro']
                        and not result['own_message'] and not result['foreign_message'])
                    values['max_attempts'] = (result['password_prompts'] == 3
                        and result['incorrect_prompts'] == 3 and peer.await_hangup(dialog))
                peer.register(expires=0)
        deadline = time.monotonic()+6
        while time.monotonic() < deadline:
            active = cli(container, 'core show channels concise')
            values['channels_cleared'] = not any(line.startswith('PJSIP/') for line in active.splitlines())
            if values['channels_cleared']:
                break
            time.sleep(.1)
        checks.update({'vm_auth_'+key+':'+tenant: value for key, value in values.items()})
        report['voicemail_auth_cases'][tenant] = values
    report['live_voicemail_auth_tested'] = all(checks[key] is True for key in required_voicemail_auth_checks())
