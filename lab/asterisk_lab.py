"""Sobe Asterisk real descartável no Docker e comprova registros SIP/TLS."""
import argparse
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import subprocess
import tempfile
import tarfile
import time

from .sip_tls import SipTLS

IMAGE = ('andrius/asterisk:22.11.0_debian-trixie@sha256:'
         'd6333b8b331563c5887b98b12da9371ef48317e657d17d81770fe085f335041d')


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(root, destination, source_commit="HEAD"):
    """Copia de forma privada; nunca roda gerador de segredos no checkout."""
    root, destination = Path(root), Path(destination)
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    conf = destination / 'asterisk'
    archive = subprocess.run(['git', '-C', str(root), 'archive', '--format=tar',
                              source_commit, 'asterisk'], capture_output=True, timeout=30)
    if archive.returncode:
        raise RuntimeError('não foi possível exportar configuração versionada')
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as source:
        members = []
        for member in source.getmembers():
            parts = PurePosixPath(member.name).parts
            if (not parts or parts[0] != 'asterisk' or '..' in parts
                    or not (member.isdir() or member.isfile())):
                raise ValueError('entrada insegura na configuração versionada')
            if len(parts) > 1 and parts[1] == 'certs':
                continue
            members.append(member)
        source.extractall(destination, members=members, filter='data')
    helpers = destination/'helpers'
    helpers.mkdir(mode=0o700)
    for filename in ('admin-api/tenants.py', 'scripts/secrets_generator.py'):
        body = command(['git', '-C', str(root), 'show', source_commit+':'+filename]).stdout
        (helpers/Path(filename).name).write_text(body)
    generator = load_file('lab_secrets_generator', helpers/'secrets_generator.py')
    content = (conf/'pjsip.conf').read_text()
    placeholders = generator.find_placeholders(content)
    secret_map = {p: generator.generate_strong_secret() for p in placeholders}
    content = generator.replace_all_placeholders(content, secret_map)
    # O laboratório não altera templates, autenticação nem contextos de produção.
    content = content.replace('bind=0.0.0.0:5060', 'bind=127.0.0.1:5060')
    content = content.replace('bind=0.0.0.0:5061', 'bind=127.0.0.1:5061')
    content = content.replace('bind=0.0.0.0', 'bind=127.0.0.1')
    (conf/'pjsip.conf').write_text(content)
    credentials = {}
    for section, text in re.findall(r'(?m)^\[([^\]]+)\][^\n]*\n((?:(?!^\[).|\n)*)', content):
        if re.search(r'(?m)^type=auth$', text):
            match = re.search(r'(?m)^password=(.+)$', text)
            credentials[section] = match[1]
    tenants = load_file('lab_tenants', helpers/'tenants.py')
    dynamic = tenants.generate_tenant_credentials('t3')
    credentials.update(dynamic)
    for folder, body in (
        ('pjsip_tenants', tenants.render_tenant_pjsip('t3', dynamic)),
        ('extensions_tenants', tenants.render_tenant_extensions('t3')),
        ('queues_tenants', tenants.render_tenant_queues('t3')),
        ('voicemail_tenants', tenants.render_tenant_voicemail('t3')),
        ('parking_tenants', tenants.render_tenant_parking('t3')),
    ):
        (conf/folder).mkdir(exist_ok=True)
        (conf/folder/'t3.conf').write_text(body)
    # Nenhum AMI fica exposto pelo laboratório de registros.
    (conf/'manager.conf').write_text('[general]\nenabled=no\n')
    http = (conf/'http.conf').read_text().replace('0.0.0.0', '127.0.0.1')
    (conf/'http.conf').write_text(http)
    (conf/'asterisk.conf').write_text('''[directories]
astetcdir => /etc/asterisk
astmoddir => /usr/lib/asterisk/modules
astvarlibdir => /var/lib/asterisk
astdbdir => /var/lib/asterisk
astkeydir => /var/lib/asterisk
astdatadir => /var/lib/asterisk
astagidir => /var/lib/asterisk/agi-bin
astspooldir => /var/spool/asterisk
astrundir => /var/run/asterisk
astlogdir => /var/log/asterisk
[options]
verbose = 0
debug = 0
''')
    (conf/'modules.conf').write_text('[modules]\nautoload=yes\n')
    (conf/'logger.conf').write_text('[logfiles]\nconsole => error,warning\n')
    certs = conf/'certs'
    certs.mkdir()
    command(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
             '-keyout', str(certs/'asterisk.key'), '-out', str(certs/'asterisk.crt'),
             '-days', '1', '-subj', '/CN=localhost',
             '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1'])
    # Nenhum dado do laboratório fica acessível para outros usuários locais.
    for path in destination.rglob('*'):
        path.chmod(0o700 if path.is_dir() else 0o600)
    return {'credentials': credentials, 'conf': conf, 'ca': certs/'asterisk.crt'}


def command(argv, *, timeout=30, check=True):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode:
        # stdout/stderr podem conter material de configuração; não publicar.
        raise RuntimeError('comando do laboratório falhou')
    return result


def cli(container, text):
    return command(['docker', 'exec', container, 'asterisk', '-rx', text]).stdout


def diagnose(raw):
    return {
        'missing_template': 'Inheritance requested, but category' in raw,
        'permission_denied': 'Permission denied' in raw,
        'database_unavailable': 'Unable to open Asterisk database' in raw,
        'config_unreadable': 'Unable to open specified master config file' in raw,
    }


def cleanup_owned(name, ownership):
    """Remove somente o ID cujo token de propriedade coincide; logs são opcionais."""
    result = {'removed': False, 'retain_staging': True, 'diagnostics': diagnose('')}
    try:
        inspected = command(['docker', 'inspect', name], check=False)
        if inspected.returncode:
            return result
        info = json.loads(inspected.stdout)[0]
        labels = info['Config'].get('Labels') or {}
        if labels.get('io.axe.pabx.lab-owner') != ownership:
            result['retain_staging'] = False  # Outro container nunca usou nossa montagem.
            return result
        container_id = info['Id']
        if not re.fullmatch(r'[0-9a-f]{64}', container_id):
            return result
    except (OSError, ValueError, TypeError, KeyError, IndexError, subprocess.TimeoutExpired):
        return result
    try:
        logs = command(['docker', 'logs', container_id], check=False, timeout=8)
        result['diagnostics'] = diagnose(logs.stdout + logs.stderr)
    except (OSError, subprocess.TimeoutExpired):
        pass
    # A remoção independe da coleta de logs e usa ID imutável, nunca só nome.
    try:
        removed = command(['docker', 'rm', '--force', '--volumes', container_id], check=False)
        result['removed'] = removed.returncode == 0
        result['retain_staging'] = not result['removed']
    except (OSError, subprocess.TimeoutExpired):
        pass
    return result


def summarize(checks, *, calls=False):
    required = {'real_runtime', 'tls_transport', 'wss_transport', 'container_removed',
                'checkout_clean', 'runtime_mounts', 'source_label'}
    required.update(name+':'+tid for tid in ('t1', 't2', 't3')
                    for name in ('context', 'register', 'contact', 'unregister', 'wrong_password'))
    if calls:
        from .call_checks import required_call_checks
        required.update(required_call_checks())
    passed = sum(value is True for value in checks.values())
    return {'passed': passed, 'total': len(checks),
            'success': set(checks) == required and passed == len(required)}


def run(root, report, *, calls=False):
    source = command(['git', '-C', str(root), 'rev-parse', 'HEAD']).stdout.strip()
    if not re.fullmatch(r'[0-9a-f]{40}', source):
        raise ValueError('SHA do checkout inválido')
    report.update(schema_version=1, kind='real_asterisk_tls_registration_lab',
                  source_commit=source, operational_go_authorized=False,
                  timestamp_utc=datetime.now(timezone.utc).isoformat(), checks={},
                  sip_call_tested=False, rtp_tested=False, srtp_tested=False,
                  live_tenant_isolation_tested=False, backup_restore_tested=False)
    if calls:
        report.update(schema_version=2, kind='real_asterisk_secure_calls_lab', dtls_tested=False,
                      wss_session_tested=False)
    clean = command(['git', '-C', str(root), 'diff', '--quiet', 'HEAD', '--',
                     'asterisk', 'admin-api/tenants.py', 'admin-api/conf_generator.py',
                     'scripts/secrets_generator.py', 'lab'], check=False)
    report['checks']['checkout_clean'] = clean.returncode == 0
    if clean.returncode != 0:
        raise RuntimeError('checkout do laboratório contém alterações não commitadas')
    name = 'axe-lab-' + secrets.token_hex(6)
    ownership = secrets.token_hex(32)
    attempted_create = False
    retain_staging = False
    folder = Path(tempfile.mkdtemp(prefix='axe-pabx-lab-'))
    try:
        prepared = prepare(root, folder/'private', source)
        if calls:
            from .call_checks import prepare_calls
            prepare_calls(root, prepared, source)
        command(['docker', 'pull', IMAGE], timeout=180)
        image_data = json.loads(command(['docker', 'image', 'inspect', IMAGE]).stdout)[0]
        report['image_id'] = image_data['Id']
        report['image_digests'] = image_data.get('RepoDigests', [])
        attempted_create = True
        result = command(['docker', 'create', '--name', name,
                         '--network', 'host', '--user', '0:0', '--cap-drop', 'ALL',
                         '--cap-add', 'DAC_OVERRIDE',
                         '--security-opt', 'no-new-privileges', '--label',
                         'io.axe.pabx.source-commit='+source, '--label',
                         'io.axe.pabx.lab-owner='+ownership,
                         '--mount', f'type=bind,src={prepared["conf"]},dst=/etc/asterisk,readonly',
                         '--entrypoint', 'asterisk', IMAGE, '-f', '-n',
                         '-C', '/etc/asterisk/asterisk.conf'], check=False)
        if result.returncode:
            raise RuntimeError('inicialização do container falhou')
        container_id = result.stdout.strip()
        if not re.fullmatch(r'[0-9a-f]{64}', container_id):
            raise RuntimeError('ID de container inválido')
        command(['docker', 'start', container_id])
        container_data = json.loads(command(['docker','inspect',container_id]).stdout)[0]
        report['checks']['source_label'] = (
            container_data['Config']['Labels'].get('io.axe.pabx.source-commit') == source
            and container_data['Image'] == image_data['Id'])
        report['checks']['runtime_mounts'] = any(
            mount.get('Type') == 'bind' and mount.get('Destination') == '/etc/asterisk'
            and mount.get('Source') == str(prepared['conf']) and mount.get('RW') is False
            for mount in container_data['Mounts'])
        ready = False
        for _ in range(40):
            result = command(['docker', 'exec', container_id, 'asterisk', '-rx',
                              'core show version'], check=False)
            if result.returncode == 0 and 'Asterisk ' in result.stdout:
                report['asterisk_version'] = result.stdout.strip().splitlines()[0]
                ready = True
                break
            time.sleep(0.5)
        report['checks']['real_runtime'] = ready
        if not ready:
            raise RuntimeError('Asterisk não ficou pronto')
        # A CLI abrir antes do PJSIP não significa que todos os módulos carregaram.
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if 't1-1001' in cli(container_id, 'pjsip show endpoints'):
                break
            time.sleep(0.5)
        report['checks']['tls_transport'] = 'transport-tls' in cli(container_id, 'pjsip show transports')
        report['checks']['wss_transport'] = 'transport-wss' in cli(container_id, 'pjsip show transports')
        for tenant, endpoint in (('t1','t1-1001'), ('t2','t2-1001'), ('t3','t3-recepcao')):
            endpoint_output = cli(container_id, f'pjsip show endpoint {endpoint}')
            report['checks']['context:'+tenant] = bool(re.search(
                r'(?im)^\s*context\s*:\s*'+tenant+r'-internal\s*$', endpoint_output))
            peer = SipTLS('127.0.0.1', 5061, prepared['ca'], endpoint,
                          prepared['credentials'][endpoint])
            try:
                report['tls_version'] = peer.connection.version()
                report['phase'] = 'register:'+tenant
                report['checks']['register:'+tenant] = peer.register() == 200
                report['checks']['contact:'+tenant] = endpoint+'/' in cli(container_id, 'pjsip show contacts')
                report['phase'] = 'unregister:'+tenant
                report['checks']['unregister:'+tenant] = peer.register(expires=0) == 200
            finally:
                peer.close()
            peer = SipTLS('127.0.0.1', 5061, prepared['ca'], endpoint, secrets.token_hex(24))
            try:
                report['phase'] = 'wrong_password:'+tenant
                report['checks']['wrong_password:'+tenant] = peer.register() in (401,403)
            finally:
                peer.close()
        if calls:
            from .call_checks import exercise_calls
            exercise_calls(container_id, prepared, report)
    finally:
        if attempted_create:
            cleaned = cleanup_owned(name, ownership)
            report['checks']['container_removed'] = cleaned['removed']
            report['startup_diagnostics'] = cleaned['diagnostics']
            retain_staging = cleaned['retain_staging']
        report['private_staging_retained'] = retain_staging
        if not retain_staging:
            shutil.rmtree(folder)
    report.update(summarize(report['checks'], calls=calls))
    return report['success']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--calls', action='store_true', help='testar chamadas, CDR e SRTP real')
    args = parser.parse_args(argv)
    report = {}
    try:
        success = run(Path(__file__).resolve().parents[1], report, calls=args.calls)
    except Exception as exc:
        success = False
        report['success'] = False
        report['error_type'] = type(exc).__name__
        known_errors = {'REGISTER inicial deve exigir autenticação': 'challenge_expected',
                        'resposta de outra transação SIP': 'transaction_mismatch',
                        'desafio REGISTER ausente ou ambíguo': 'challenge_missing',
                        'Content-Length SIP inválido': 'content_length_invalid',
                        'INVITE inicial deve exigir autenticação': 'invite_challenge_expected',
                        'contato SIP fora do loopback': 'contact_not_loopback',
                        'SDP do laboratório deve ser SRTP loopback': 'sdp_not_secure_loopback',
                        'perfil SDP não suportado': 'sdp_profile_unsupported',
                        'conteúdo PCMU divergente': 'pcmu_content_mismatch',
                        'origem de mídia inesperada': 'media_source_mismatch'}
        report['error_reason'] = known_errors.get(str(exc), 'other')
        if re.fullmatch(r'chamada SIP rejeitada: [0-9]{3}', str(exc)):
            report['error_reason'] = 'call_rejected_'+str(exc)[-3:]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    checks = report.get('checks', {})
    print(f"Asterisk real: {sum(checks.values())}/{len(checks)} verificações; "
          f"resultado={'PASS' if success else 'FAIL'}")
    for key, passed in checks.items():
        print(f"  {key}: {'PASS' if passed else 'FAIL'}")
    if report.get('error_type'):
        print('Falha: '+report['error_type']+' / '+report['error_reason'])
    if report.get('phase'):
        print('Etapa: '+report['phase'])
    for call, events in report.get('call_protocol', {}).items():
        print('Protocolo '+call+': '+json.dumps(events, sort_keys=True))
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
