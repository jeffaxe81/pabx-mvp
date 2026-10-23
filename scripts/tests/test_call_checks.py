"""Aceite fechado: CDR coerente e configuração privada produzida pelo gerador real."""
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def test_cdr_requires_answered_correct_tenant_context_endpoints_and_duration():
    from lab.call_checks import cdr_matches
    row = '"t1","1001","1002","t1-internal","PJSIP/t1-1001-00000001","PJSIP/t1-1002-00000002","ANSWERED","1","123.45"\n'
    assert cdr_matches(row, 't1', '1001', '1002') is True
    for before, after in [('"t1",', '"t2",'), ('t1-internal', 't2-internal'),
                          ('PJSIP/t1-1002-', 'PJSIP/t2-1002-'), ('ANSWERED', 'NO ANSWER'),
                          ('"1","123.45"', '"0","123.45"'), ('"1001",', '"9999",')]:
        assert cdr_matches(row.replace(before, after), 't1', '1001', '1002') is False
    for raw in ('', 'garbage', row.replace(',"123.45"', ''), row+'"unterminated'):
        assert cdr_matches(raw, 't1', '1001', '1002') is False


def test_calls_summary_requires_every_direction_and_never_upgrades_dtls():
    from lab.asterisk_lab import summarize
    from lab.call_checks import required_call_checks
    baseline = {'real_runtime', 'tls_transport', 'wss_transport', 'container_removed',
                'checkout_clean', 'runtime_mounts', 'source_label'}
    baseline.update(name+':'+tenant for tenant in ('t1','t2','t3')
                    for name in ('context','register','contact','unregister','wrong_password'))
    complete = {name: True for name in baseline | required_call_checks()}
    assert summarize(complete, calls=True)['success'] is True
    assert summarize({key:value for key,value in complete.items() if key != 'cdr:t2:reverse'}, calls=True)['success'] is False
    assert summarize({**complete, 'srtp:t3:forward': False}, calls=True)['success'] is False
    assert summarize({**complete, 'cdr:t1:forward': 1}, calls=True)['success'] is False
    assert summarize(complete)['success'] is False


def test_call_preparation_generates_secure_t2_t3_without_changing_static_source(tmp_path):
    from lab.asterisk_lab import prepare
    from lab.call_checks import prepare_calls
    root = tmp_path/'repo'
    shutil.copytree(ROOT/'asterisk', root/'asterisk')
    for name in ('admin-api/tenants.py','admin-api/conf_generator.py','scripts/secrets_generator.py'):
        target = root/name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(ROOT/name, target)
    for args in (['init','-q'], ['add','.'], ['-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','fixture']):
        subprocess.run(['git','-C',str(root),*args],check=True,capture_output=True)
    before = (root/'asterisk/pjsip.conf').read_bytes()
    prepared = prepare(root, tmp_path/'private')
    prepare_calls(root, prepared, 'HEAD')
    assert (root/'asterisk/pjsip.conf').read_bytes() == before
    dynamic = (prepared['conf']/'generated/pjsip_dynamic.conf').read_text()
    for name in ('t2-1002', 't3-1001', 't3-1002'):
        assert f'[{name}](endpoint-secure)' in dynamic
        assert len(prepared['credentials'][name]) >= 24
    assert (prepared['conf']/'cdr_custom.conf').stat().st_mode & 0o077 == 0
    assert 'CDR(accountcode)=t2' in (prepared['conf']/'generated/extensions_dynamic_dial-t2.conf').read_text()


def test_cli_writes_sanitized_failure_report_for_libsrtp_error(tmp_path, monkeypatch, capsys):
    import json
    import pylibsrtp
    from lab import asterisk_lab
    def fail(*args, **kwargs):
        raise pylibsrtp.Error('PRIVATE_SDES_KEY')
    monkeypatch.setattr(asterisk_lab, 'run', fail)
    output = tmp_path/'result.json'
    assert asterisk_lab.main(['--calls','--report',str(output)]) == 1
    report = json.loads(output.read_text())
    assert report['success'] is False
    assert report['error_type'] == 'Error'
    assert 'PRIVATE_SDES_KEY' not in output.read_text()+capsys.readouterr().out
