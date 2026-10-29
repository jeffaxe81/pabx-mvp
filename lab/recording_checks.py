"""Aceite MixMonitor -> CDR confiável -> catálogo -> HTTP, só dados sintéticos.

Áudio, manifesto, nomes e tokens permanecem na pasta privada descartável.
O relatório publica apenas resultados booleanos por empresa.
"""
import csv
import hashlib
import io
import json
from pathlib import Path
import secrets
import sys
import threading
import time
import urllib.error
import urllib.request
import wave
from http.server import ThreadingHTTPServer

TENANTS = ('t1', 't2', 't3', 't10')
HTTP_CHECKS = ('catalog_applied', 'http_owner_list', 'http_owner_audio',
               'http_supervisor', 'http_admin', 'http_other_agent',
               'http_cross_tenant', 'http_anonymous', 'http_bad_origin', 'http_revoked')
CHECKS = ('recording_call', 'recording_cdr', 'recording_audio', *HTTP_CHECKS)


def required_recording_checks():
    return {f'{metric}:{tenant}' for tenant in TENANTS for metric in CHECKS}


def recording_cdr_events(raw):
    """Exporta apenas registros inteiros da trilha CDR privada do Asterisk."""
    if not isinstance(raw, str) or not raw or len(raw) > 1024*1024:
        raise ValueError('CDR de gravação ausente ou excessivo')
    try:
        rows = list(csv.reader(io.StringIO(raw), strict=True))
    except csv.Error as exc:
        raise ValueError('CDR de gravação malformado') from exc
    if not rows or any(len(row) != 10 for row in rows):
        raise ValueError('campos CDR de gravação inválidos')
    names = ('AccountCode', 'CallerIDNum', 'Destination', 'DestinationContext',
             'Channel', 'DestinationChannel', 'Disposition', 'BillableSeconds',
             'UniqueID', 'StartTime')
    return [{'Event': 'Cdr', **dict(zip(names, row))} for row in rows]


def recorded_audio_valid(path):
    """Cabeçalho válido, pelo menos 0,5s e amostras PCM não silenciosas."""
    try:
        with wave.open(str(path), 'rb') as audio:
            if (audio.getnchannels() not in (1, 2) or audio.getsampwidth() != 2
                    or audio.getframerate() != 8000 or audio.getnframes() < 4000):
                return False
            frames = audio.readframes(audio.getnframes())
            return any(frames) and len(frames) >= 8000
    except (OSError, ValueError, EOFError, wave.Error):
        return False


def prepare_recordings(root, prepared, source_commit):
    from .asterisk_lab import command, load_file
    conf = prepared['conf']
    helper = conf.parent/'helpers/recording_conf_generator.py'
    helper.write_text(command(['git', '-C', str(root), 'show',
                              source_commit+':admin-api/conf_generator.py']).stdout)
    helper.chmod(0o600)
    generator = load_file('lab_recording_generator', helper)
    extensions = []
    for tenant in TENANTS:
        for number in ('1101', '1102'):
            name = tenant+'-'+number
            password = secrets.token_urlsafe(32)
            prepared['credentials'][name] = password
            extensions.append({'name': name, 'number': number, 'tenant': tenant,
                               'password': password, 'display_name': 'Private Recording Lab',
                               'voicemail_pin': str(secrets.randbelow(90000000)+10000000)})
    for filename, body in generator.render_all(extensions, tenant_ids=TENANTS).items():
        target = conf/'generated'/filename
        with target.open('a') as output:
            output.write('\n'+body)
        target.chmod(0o600)
    fields = ('accountcode', 'src', 'dst', 'dcontext', 'channel', 'dstchannel',
              'disposition', 'billsec', 'uniqueid', 'start')
    with (conf/'cdr_custom.conf').open('a') as output:
        output.write('Recording.csv => '+','.join(
            '${CSV_QUOTE(${CDR('+field+')})}' for field in fields)+'\n')


def exercise_recording_http(root, staging, audio_dir, rows):
    """Usa importador e Handler de produção; servidor fica só no loopback."""
    from .asterisk_lab import load_file
    queue_path = str(Path(root)/'queue-api')
    sys.path.insert(0, queue_path)
    try:
        import recording_catalog
        server = load_file('lab_recording_http_server', Path(queue_path)/'server.py')
    finally:
        sys.path.remove(queue_path)
    policy_path = Path(staging)/'recording_access.json'
    manifest_path = Path(staging)/'recording_manifest.jsonl'
    policy = {'credentials': [], 'recordings': {}}
    tokens = {}
    for tenant in TENANTS:
        for kind in ('owner', 'other_agent', 'supervisor', 'admin'):
            token = secrets.token_urlsafe(48)
            tokens[tenant, kind] = token
            credential = {'tenant': tenant, 'role': 'agent' if kind in ('owner', 'other_agent') else kind,
                          'expires_at': time.time()+900,
                          'token_sha256': hashlib.sha256(token.encode('ascii')).hexdigest()}
            if credential['role'] == 'agent':
                credential['extension'] = tenant+('-1102' if kind == 'owner' else '-1101')
            policy['credentials'].append(credential)
    recording_catalog.atomic_save(policy_path, (json.dumps(policy)+'\n').encode())
    manifest_path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    manifest_path.chmod(0o600)
    imported = recording_catalog.reconcile_catalog(policy_path, audio_dir, manifest_path, apply=True)
    server.RECORDINGS_DIR = str(audio_dir)
    server.RECORDINGS_ACCESS_POLICY_PATH = str(policy_path)
    server.RECORDINGS_CORS_ORIGINS = {'http://localhost:8082'}

    class QuietHandler(server.Handler):
        def log_message(self, *_):
            pass

    http = ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    base = 'http://127.0.0.1:'+str(http.server_address[1])

    def request(path, token=None, origin=None):
        headers = {}
        if token is not None:
            headers['Authorization'] = 'Bearer '+token
        if origin is not None:
            headers['Origin'] = origin
        req = urllib.request.Request(base+path, headers=headers)
        try:
            response = urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.code, dict(response.headers), response.read()

    results = {}
    try:
        for row in rows:
            tenant, filename = row['tenant'], row['filename']
            path = '/recordings/'+filename
            own = tokens[tenant, 'owner']
            status, headers, payload = request('/api/recordings', own)
            listing = json.loads(payload).get('recordings', [])
            status_audio, audio_headers, audio = request(path, own)
            expected = (Path(audio_dir)/filename).read_bytes()
            other_status, _, other_listing = request('/api/recordings', tokens[tenant, 'other_agent'])
            cross = []
            for other in TENANTS:
                if other == tenant:
                    continue
                for role in ('owner', 'supervisor', 'admin'):
                    token = tokens[other, role]
                    code, _, body = request('/api/recordings', token)
                    cross.append(code == 200 and filename not in {
                        item['filename'] for item in json.loads(body).get('recordings', [])}
                        and request(path, token)[0] == 404)
            current = {
                'catalog_applied': imported['mode'] == 'applied' and imported['new'] == len(rows),
                'http_owner_list': status == 200 and headers.get('Cache-Control') == 'no-store'
                    and [item['filename'] for item in listing] == [filename],
                'http_owner_audio': status_audio == 200 and audio == expected
                    and audio_headers.get('Cache-Control') == 'no-store',
                'http_supervisor': request(path, tokens[tenant, 'supervisor'])[2] == expected,
                'http_admin': request(path, tokens[tenant, 'admin'])[2] == expected,
                'http_other_agent': other_status == 200 and json.loads(other_listing).get('recordings') == []
                    and request(path, tokens[tenant, 'other_agent'])[0] == 404,
                'http_cross_tenant': all(cross),
                'http_anonymous': request(path)[0] == 401 and request('/api/recordings')[0] == 401,
                'http_bad_origin': request(path, own, 'https://untrusted.invalid')[0] == 403,
            }
            results[tenant] = current
        # Finish every cross-tenant assertion before revoking any bearer.
        # Otherwise a previous tenant's revoked owner yields 401 and masks
        # the intended authenticated 404 boundary check on the next tenant.
        for row in rows:
            tenant, filename = row['tenant'], row['filename']
            own = tokens[tenant, 'owner']
            path = '/recordings/'+filename
            active = recording_catalog.read_policy_secure(policy_path)
            digest = hashlib.sha256(own.encode('ascii')).hexdigest()
            active['credentials'] = [item for item in active['credentials'] if item['token_sha256'] != digest]
            recording_catalog.atomic_save(policy_path, (json.dumps(active)+'\n').encode())
            results[tenant]['http_revoked'] = (request(path, own)[0] == 401
                and request('/api/recordings', own)[0] == 401
                and request(path, tokens[tenant, 'supervisor'])[0] == 200)
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=3)
    return results


def exercise_recordings(root, container, prepared, report):
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import ExitStack
    from .asterisk_lab import command
    from .sip_calls import CallPeer
    from .srtp_media import SrtpMedia, exchange

    checks = report['checks']
    checks.update({key: False for key in required_recording_checks()})
    report['live_recording_access_tested'] = False
    report['recording_cases'] = {}
    command(['docker', 'exec', container, 'mkdir', '-p', '/var/spool/asterisk/monitor',
             '/var/log/asterisk/cdr-custom'])
    for tenant in TENANTS:
        report['phase'] = 'recording-call:'+tenant
        with ExitStack() as resources, ThreadPoolExecutor(max_workers=1) as executor:
            caller = CallPeer('127.0.0.1', 5061, prepared['ca'], tenant+'-1101',
                              prepared['credentials'][tenant+'-1101'])
            callee = CallPeer('127.0.0.1', 5061, prepared['ca'], tenant+'-1102',
                              prepared['credentials'][tenant+'-1102'])
            resources.callback(caller.close)
            resources.callback(callee.close)
            left, right = SrtpMedia(), SrtpMedia()
            resources.callback(left.close)
            resources.callback(right.close)
            registered = caller.register() == 200 and callee.register() == 200
            pending = executor.submit(callee.answer, right)
            caller_dialog = caller.dial('1102', left)
            callee_dialog = pending.result(timeout=14)
            media = exchange(left, right, duration=2)
            pending = executor.submit(callee.await_hangup, callee_dialog)
            hungup = caller.hangup(caller_dialog) == 200 and pending.result(timeout=12)
            checks['recording_call:'+tenant] = registered and hungup and media['authenticated'] and media['payloads_match']
            caller.register(expires=0)
            callee.register(expires=0)
    report['phase'] = 'recording-cdr-catalog-http'
    staging = prepared['conf'].parent
    audio_dir = staging/'recorded_audio'
    audio_dir.mkdir(mode=0o700)
    # Docker cp keeps bytes unchanged; no áudio leaves the disposable folder.
    command(['docker', 'cp', container+':/var/spool/asterisk/monitor/.', str(audio_dir)])
    deadline = time.monotonic()+8
    events = []
    while time.monotonic() < deadline:
        raw = command(['docker', 'exec', container, 'cat',
                       '/var/log/asterisk/cdr-custom/Recording.csv'], check=False)
        if raw.returncode == 0:
            events = recording_cdr_events(raw.stdout)
            if all(any(event['AccountCode'] == tenant and event['CallerIDNum'] == '1101'
                       and event['Destination'] == '1102' for event in events) for tenant in TENANTS):
                break
        time.sleep(.2)
    sys.path.insert(0, str(Path(root)/'queue-api'))
    try:
        from recording_cdr_candidates import propose_candidates, corroborate_cdr
    finally:
        sys.path.remove(str(Path(root)/'queue-api'))
    candidates, summary = propose_candidates(audio_dir, events)
    selected = [row for row in candidates if row.get('owner_extension') == row['tenant']+'-1102']
    for tenant in TENANTS:
        matching = [row for row in selected if row['tenant'] == tenant]
        checks['recording_cdr:'+tenant] = len(matching) == 1 and any(
            corroborate_cdr(event) is not None and event['AccountCode'] == tenant
            and event['CallerIDNum'] == '1101' and event['Destination'] == '1102'
            and 'CDR:'+event['UniqueID'] == matching[0]['source_ref'] for event in events)
        checks['recording_audio:'+tenant] = len(matching) == 1 and recorded_audio_valid(audio_dir/matching[0]['filename'])
    if not all(checks['recording_cdr:'+tenant] and checks['recording_audio:'+tenant] for tenant in TENANTS):
        raise RuntimeError('gravação real sem vínculo CDR inequívoco e áudio válido')
    results = exercise_recording_http(root, staging, audio_dir, selected)
    for tenant, metrics in results.items():
        checks.update({metric+':'+tenant: value for metric, value in metrics.items()})
        report['recording_cases'][tenant] = dict(metrics)
    report['live_recording_access_tested'] = all(
        checks[key] is True for key in required_recording_checks())
