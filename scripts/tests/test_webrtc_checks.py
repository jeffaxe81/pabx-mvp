"""Contratos fechados de relatório e CDR do telefone web real."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))


def test_browser_report_requires_all_named_checks_and_six_unique_cases():
    from lab.webrtc_checks import browser_checks, validate_browser_report
    cases = [{'tenant':tenant,'direction':direction,
              'left':{'packets_sent':80,'packets_received':75,'dtls':True,'srtp':True,'rtp':True,
                      'cipher':'AES_CM_128_HMAC_SHA1_80','peak_hz':880,'rms':0.1,'audio_attached':True,'local_ice':True},
              'right':{'packets_sent':76,'packets_received':79,'dtls':True,'srtp':True,'rtp':True,
                       'cipher':'AES_CM_128_HMAC_SHA1_80','peak_hz':440,'rms':0.1,'audio_attached':True,'local_ice':True}}
             for tenant in ('t1','t2','t3') for direction in ('forward','reverse')]
    report = {'schema_version':1,'success':True,'checks':{key:True for key in browser_checks()},'cases':cases,
              'browser_version':'Chrome/130.0.0.0'}
    assert validate_browser_report(report)['checks']['webrtc_browser_closed'] is True
    import copy
    for mutate in (lambda r:r['checks'].pop('webrtc_dtls:t2:forward'),
                   lambda r:r['checks'].update({'webrtc_dtls:t1:forward':1}),
                   lambda r:r['cases'].pop(),
                   lambda r:r['cases'].append(r['cases'][0]),
                   lambda r:r['cases'][0]['left'].update(packets_received=0),
                   lambda r:r['cases'][0]['left'].update(peak_hz=440),
                   lambda r:r.update(private_key='PRIVATE_MATERIAL')):
        invalid = copy.deepcopy(report)
        mutate(invalid)
        with pytest.raises(ValueError):
            validate_browser_report(invalid)


def test_webrtc_cdr_matches_operator_endpoint_names_with_exact_tenant():
    from lab.webrtc_checks import webrtc_cdr_matches
    row = '"t2","1010","1011","t2-internal","PJSIP/t2-recepcao-00000001","PJSIP/t2-recepcao-2-00000002","ANSWERED","2","123.45"\n'
    assert webrtc_cdr_matches(row,'t2','1010','1011') is True
    assert webrtc_cdr_matches(row.replace('PJSIP/t2-recepcao-2-', 'PJSIP/t1-recepcao-2-'),'t2','1010','1011') is False
    assert webrtc_cdr_matches(row.replace('ANSWERED','NO ANSWER'),'t2','1010','1011') is False


def test_webrtc_summary_requires_media_cases_and_cleanup_beyond_prior_calls():
    from lab.asterisk_lab import summarize
    from lab.webrtc_checks import required_webrtc_checks
    from lab.call_checks import required_call_checks
    names = {'real_runtime','tls_transport','wss_transport','container_removed','checkout_clean','runtime_mounts','source_label'}
    names.update(name+':'+tenant for tenant in ('t1','t2','t3')
                 for name in ('context','register','contact','unregister','wrong_password'))
    names.update(required_call_checks())
    prior = {name:True for name in names}
    assert summarize(prior,calls=True,webrtc=True)['success'] is False
    complete = {**prior,**{name:True for name in required_webrtc_checks()}}
    assert summarize(complete,calls=True,webrtc=True)['success'] is True
    assert summarize({**complete,'webrtc_tone:t3:reverse':False},calls=True,webrtc=True)['success'] is False
