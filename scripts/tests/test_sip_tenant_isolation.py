"""Testes de contrato do laboratório de tentativas SIP entre empresas."""
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

VALID_REJECTION = ('"","1001","t2-1001","t1-internal",'
                   '"PJSIP/t1-1001-00000001","","FAILED","0","123.46"\n')


def test_cross_tenant_cdr_requires_new_isolated_rejection():
    from lab.tenant_isolation_checks import rejected_cdr_is_isolated
    assert rejected_cdr_is_isolated(VALID_REJECTION, set(), 't1-1001', 't2-1001')
    assert not rejected_cdr_is_isolated(VALID_REJECTION, {'123.46'}, 't1-1001', 't2-1001')
    for before, after in (
        ('t1-internal', 't2-internal'),
        ('PJSIP/t1-1001-', 'PJSIP/t2-1001-'),
        ('"t2-1001"', '"t1-1001"'),
        ('"FAILED"', '"ANSWERED"'),
        ('"0","123.46"', '"1","123.46"'),
        ('00000001",""', '00000001","PJSIP/t2-1001-00000002"'),
    ):
        altered = VALID_REJECTION.replace(before, after)
        assert altered != VALID_REJECTION
        assert not rejected_cdr_is_isolated(altered, set(), 't1-1001', 't2-1001')
    assert not rejected_cdr_is_isolated('', set(), 't1-1001', 't2-1001')
    assert not rejected_cdr_is_isolated('garbage', set(), 't1-1001', 't2-1001')
    assert not rejected_cdr_is_isolated(VALID_REJECTION, None, 't1-1001', 't2-1001')
    assert not rejected_cdr_is_isolated(
        VALID_REJECTION + VALID_REJECTION.replace('123.46', '123.47').replace(
            '"FAILED"', '"ANSWERED"'), set(), 't1-1001', 't2-1001')


def test_isolation_summary_requires_all_cases_and_real_sip_contexts():
    from lab.asterisk_lab import summarize
    from lab.call_checks import required_call_checks
    from lab.tenant_isolation_checks import required_isolation_checks, CROSS_CASES
    baseline = {'real_runtime', 'tls_transport', 'wss_transport',
                'container_removed', 'checkout_clean', 'runtime_mounts', 'source_label'}
    baseline.update(name + ':' + tenant for tenant in ('t1', 't2', 't3')
                    for name in ('context', 'register', 'contact', 'unregister', 'wrong_password'))
    checks = {name: True for name in baseline | required_call_checks()
              | required_isolation_checks()}
    assert len(CROSS_CASES) >= 3
    assert summarize(checks, calls=True, isolation=True)['success'] is True
    assert summarize(checks, calls=True)['success'] is False
    for name in required_isolation_checks():
        assert not summarize({k: v for k, v in checks.items() if k != name},
                             calls=True, isolation=True)['success']
        assert not summarize({**checks, name: False},
                             calls=True, isolation=True)['success']
        assert not summarize({**checks, name: 1},
                             calls=True, isolation=True)['success']


def test_isolation_mode_requires_real_calls(tmp_path):
    from lab.asterisk_lab import main
    with pytest.raises(SystemExit) as exc:
        main(['--isolation', '--report', str(tmp_path/'report.json')])
    assert exc.value.code == 2


def test_isolation_report_never_claims_global_acceptance(tmp_path, monkeypatch):
    from lab import asterisk_lab
    def fake(root, report, *, calls=False, webrtc=False, dids=False, isolation=False):
        assert calls and isolation
        report.update(
            success=True, live_sip_extension_isolation_tested=True,
            live_tenant_isolation_tested=False, operational_go_authorized=False,
        )
        return True
    monkeypatch.setattr(asterisk_lab, 'run', fake)
    output = tmp_path/'report.json'
    assert asterisk_lab.main(['--calls', '--isolation', '--report', str(output)]) == 0
    report = json.loads(output.read_text())
    assert report['live_sip_extension_isolation_tested']
    assert report['live_tenant_isolation_tested'] is False
    assert report['operational_go_authorized'] is False


def test_isolation_ci_job_has_no_deploy_or_secrets():
    import yaml
    path = ROOT/'.github/workflows/asterisk-lab.yml'
    job = yaml.safe_load(path.read_text())['jobs']['tenant-isolation']
    body = '\n'.join(step.get('run', '') for step in job['steps'])
    assert '--calls --isolation --report' in body
    assert 'actions/upload-artifact@v4' in [
        step.get('uses') for step in job['steps']
    ]
    assert 'deploy' not in body.lower()
    assert 'secrets.' not in body
