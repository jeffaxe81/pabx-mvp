"""The full access acceptance must execute and preserve sanitized evidence."""
from pathlib import Path

import yaml


def test_access_homologation_job_runs_real_modes_and_keeps_report_on_failure():
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root/'.github/workflows/asterisk-lab.yml').read_text(encoding='utf-8'))
    job = workflow['jobs']['access-homologation']
    assert job['runs-on'] == 'ubuntu-24.04'
    commands = '\n'.join(step.get('run', '') for step in job['steps'])
    assert 'python3 -m lab.asterisk_lab --calls --recordings --voicemail-auth' in commands
    artifact = next(step for step in job['steps']
                    if step.get('uses') == 'actions/upload-artifact@v4')
    assert artifact['if'] == 'always()'
    assert artifact['with']['path'] == 'lab-results/access-homologation.json'
    assert artifact['with']['if-no-files-found'] == 'error'
