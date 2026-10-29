"""DID acceptance needs complete private CEL and correlated CDR evidence."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))


def test_did_acceptance_requires_a_complete_cel_proof_for_each_scenario():
    from lab.asterisk_lab import summarize
    from lab.did_checks import required_did_checks
    from lab.call_checks import required_call_checks
    names = {'real_runtime','tls_transport','wss_transport','container_removed',
             'checkout_clean','runtime_mounts','source_label'}
    names.update(name+':'+tenant for tenant in ('t1','t2','t3')
                 for name in ('context','register','contact','unregister','wrong_password'))
    names.update(required_call_checks())
    names.update(required_did_checks())
    expected = {'did_cel_backend'} | {'did_cel:'+case for case in
        ('static-t1','static-t2','dynamic-t3','unknown','deleted','orphan')}
    assert expected <= names
    complete = {name:True for name in names}
    from lab.recording_checks import required_recording_checks
    from lab.recording_http_checks import required_recording_http_checks
    from lab.direct_route_recording_checks import required_direct_route_checks
    assert len(complete) == (113 + len(required_recording_checks())
                             + len(required_recording_http_checks())
                             + len(required_direct_route_checks()))
    assert summarize(complete,calls=True,dids=True)['success'] is True
    for key in expected:
        assert summarize({name:value for name,value in complete.items() if name!=key},calls=True,dids=True)['success'] is False
        assert summarize({**complete,key:False},calls=True,dids=True)['success'] is False


def test_cel_preparation_is_private_and_preserves_the_real_dialplan(tmp_path):
    from lab.did_checks import prepare_dids
    conf = tmp_path/'asterisk'; conf.mkdir()
    (conf/'pjsip.conf').write_text('[existing]\n')
    (conf/'extensions.conf').write_text('ORIGINAL_ROUTE\n')
    prepared = {'conf':conf,'credentials':{}}
    prepare_dids(tmp_path,prepared,'HEAD')
    assert (conf/'extensions.conf').read_text()=='ORIGINAL_ROUTE\n'
    assert (conf/'pjsip.conf').read_text().startswith('[existing]\n')
    assert 'events=ALL' in (conf/'cel.conf').read_text()
    apps = (conf/'cel.conf').read_text().split('apps=',1)[1].splitlines()[0].split(',')
    assert {'Dial','Answer','Set','GotoIf','Hangup','Queue','Record','VoiceMail','MixMonitor','AGI','System'} <= set(apps)
    assert 'all' not in apps
    assert 'CHANNEL(linkedid)' in (conf/'cel_custom.conf').read_text()
    for name in ('cel.conf','cel_custom.conf'):
        assert (conf/name).stat().st_mode & 0o077==0


def test_cel_cursor_refuses_missing_replaced_or_partial_previous_content():
    from lab.did_evidence import new_trace
    before = 'old record\n'
    assert new_trace(before,before+'new record\n')=='new record\n'
    for after in ('','different record\n'):
        with pytest.raises(ValueError): new_trace(before,after)
    with pytest.raises(ValueError): new_trace('partial','partialnext\n')


def test_backend_requires_actual_application_tracking_not_the_literal_all():
    from lab.did_evidence import cel_backend_status, TRACKED_APPS
    modules = 'cel_custom.so Custom CEL backend\n'
    status = 'CEL Logging: Enabled\n'+''.join('CEL Tracking Application: '+app.lower()+'\n' for app in TRACKED_APPS)
    assert all(cel_backend_status(modules,status).values())
    assert not all(cel_backend_status(modules,'CEL Logging: Enabled\nCEL Tracking Application: all\n').values())
    assert not all(cel_backend_status(modules,status.replace('Enabled','Disabled')).values())
    assert not all(cel_backend_status('',status).values())
