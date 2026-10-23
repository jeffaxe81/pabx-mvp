"""Sobe Asterisk real descartável no Docker e comprova registros SIP/TLS."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import time

from .sip_tls import SipTLS

IMAGE = 'andrius/asterisk:22.11.0_debian-trixie'


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(root, destination):
    """Copia de forma privada; nunca roda gerador de segredos no checkout."""
    root, destination = Path(root), Path(destination)
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    conf = destination / 'asterisk'
    shutil.copytree(root / 'asterisk', conf,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'certs'))
    generator = load_file('lab_secrets_generator', root/'scripts/secrets_generator.py')
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
    tenants = load_file('lab_tenants', root/'admin-api/tenants.py')
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


def summarize(checks):
    required = {'real_runtime', 'tls_transport', 'wss_transport', 'container_removed'}
    required.update(name+':'+tid for tid in ('t1', 't2', 't3')
                    for name in ('context', 'register', 'contact', 'unregister', 'wrong_password'))
    passed = sum(value is True for value in checks.values())
    return {'passed': passed, 'total': len(checks),
            'success': set(checks) == required and passed == len(required)}


def run(root, report):
    source = command(['git', '-C', str(root), 'rev-parse', 'HEAD']).stdout.strip()
    if not re.fullmatch(r'[0-9a-f]{40}', source):
        raise ValueError('SHA do checkout inválido')
    report.update(schema_version=1, kind='real_asterisk_tls_registration_lab',
                  source_commit=source, operational_go_authorized=False,
                  timestamp_utc=datetime.now(timezone.utc).isoformat(), checks={},
                  sip_call_tested=False, rtp_tested=False, srtp_tested=False,
                  live_tenant_isolation_tested=False, backup_restore_tested=False)
    name = 'axe-lab-' + secrets.token_hex(6)
    started = False
    with tempfile.TemporaryDirectory(prefix='axe-pabx-lab-') as folder:
        prepared = prepare(root, Path(folder)/'private')
        try:
            command(['docker', 'pull', IMAGE], timeout=180)
            image_data = json.loads(command(['docker', 'image', 'inspect', IMAGE]).stdout)[0]
            report['image_id'] = image_data['Id']
            report['image_digests'] = image_data.get('RepoDigests', [])
            result = command(['docker', 'run', '--detach', '--name', name,
                             '--network', 'host', '--user', '0:0', '--cap-drop', 'ALL',
                             '--security-opt', 'no-new-privileges', '--label',
                             'io.axe.pabx.source-commit='+source,
                             '--mount', f'type=bind,src={prepared["conf"]},dst=/etc/asterisk,readonly',
                             '--entrypoint', 'asterisk', IMAGE, '-f', '-n',
                             '-C', '/etc/asterisk/asterisk.conf'], check=False)
            # Mesmo um docker run que falha pode ter criado o container.
            started = True
            if result.returncode:
                raise RuntimeError('inicialização do container falhou')
            ready = False
            for _ in range(40):
                result = command(['docker', 'exec', name, 'asterisk', '-rx',
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
                if 't1-1001' in cli(name, 'pjsip show endpoints'):
                    break
                time.sleep(0.5)
            report['checks']['tls_transport'] = 'transport-tls' in cli(name, 'pjsip show transports')
            report['checks']['wss_transport'] = 'transport-wss' in cli(name, 'pjsip show transports')
            for tenant, endpoint in (('t1','t1-1001'), ('t2','t2-1001'), ('t3','t3-recepcao')):
                endpoint_output = cli(name, f'pjsip show endpoint {endpoint}')
                report['checks']['context:'+tenant] = bool(re.search(
                    r'(?im)^\s*context\s*:\s*'+tenant+r'-internal\s*$', endpoint_output))
                peer = SipTLS('127.0.0.1', 5061, prepared['ca'], endpoint,
                              prepared['credentials'][endpoint])
                try:
                    report['tls_version'] = peer.connection.version()
                    report['checks']['register:'+tenant] = peer.register() == 200
                    report['checks']['contact:'+tenant] = endpoint+'/' in cli(name, 'pjsip show contacts')
                    report['checks']['unregister:'+tenant] = peer.register(expires=0) == 200
                finally:
                    peer.close()
                peer = SipTLS('127.0.0.1', 5061, prepared['ca'], endpoint, secrets.token_hex(24))
                try:
                    report['checks']['wrong_password:'+tenant] = peer.register() in (401,403)
                finally:
                    peer.close()
        finally:
            if started:
                logs = command(['docker','logs',name], check=False)
                raw = logs.stdout + logs.stderr
                report['startup_diagnostics'] = [line[:250] for line in raw.splitlines()
                    if any(term in line for term in ('does not exist', 'Unable to open', 'Unable to load',
                        'Unable to create', 'No such file', 'Permission denied', 'Cannot open', 'not found'))
                    and not any(term in line.lower() for term in ('password', 'secret', 'auth', 'nonce'))][:12]
                # Somente erros com nomes de templates; nunca linhas SIP, chaves ou áudio.
                report['missing_templates'] = sorted(set(re.findall(
                    r"Inheritance requested, but category '([A-Za-z0-9_!,-]+)' does not exist", raw)))
                cleaned = command(['docker','rm','--force',name], check=False)
                report['checks']['container_removed'] = cleaned.returncode == 0
    report.update(summarize(report['checks']))
    return report['success']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args(argv)
    report = {}
    try:
        success = run(Path(__file__).resolve().parents[1], report)
    except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.TimeoutExpired) as exc:
        success = False
        report['success'] = False
        report['error_type'] = type(exc).__name__
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    checks = report.get('checks', {})
    print(f"Asterisk real: {sum(checks.values())}/{len(checks)} verificações; "
          f"resultado={'PASS' if success else 'FAIL'}")
    for key, passed in checks.items():
        print(f"  {key}: {'PASS' if passed else 'FAIL'}")
    if report.get('error_type'):
        print('Falha: '+report['error_type'])
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
