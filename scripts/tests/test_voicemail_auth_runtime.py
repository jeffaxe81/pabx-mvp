"""Tests for synthetic media and private staging of real voicemail checks."""
from pathlib import Path
import sys
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def test_tone_detector_distinguishes_both_markers_and_rejects_silence():
    from lab.voicemail_auth_runtime import tone_flags
    from lab.srtp_media import TONES
    assert tone_flags(TONES[0]) == (True, False)
    assert tone_flags(TONES[1]) == (False, True)
    assert tone_flags(b'\xff' * 160) == (False, False)
    assert tone_flags(b'') == (False, False)


def test_prepare_adds_t10_without_overwriting_existing_generated_config(tmp_path):
    from lab.asterisk_lab import prepare
    from lab.voicemail_auth_runtime import prepare_voicemail_auth, required_voicemail_auth_checks
    root = Path(__file__).resolve().parents[2]
    prepared = prepare(root, tmp_path/'staging')
    previous = (prepared['conf']/'generated/pjsip_dynamic.conf').read_text()
    prepare_voicemail_auth(root, prepared, 'HEAD')
    conf = prepared['conf']
    assert (conf/'generated/pjsip_dynamic.conf').read_text().startswith(previous)
    assert '[t10-1001](endpoint-secure)' in (conf/'generated/pjsip_dynamic.conf').read_text()
    assert 'VoiceMailMain(${VM_ENDPOINT}@t10)' in (conf/'extensions_tenants/t10.conf').read_text()
    assert set(prepared['voicemail_auth_pins']) == {'t1', 't10'}
    assert len(set(prepared['voicemail_auth_pins'].values())) == 2
    for tenant in ('t1', 't10'):
        inbox = prepared['voicemail_auth_seed']/tenant/(tenant+'-1001')/'INBOX'
        with wave.open(str(inbox/'msg0000.wav'), 'rb') as audio:
            assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (1, 2, 8000)
            assert audio.getnframes() == 24000
        assert '[message]' in (inbox/'msg0000.txt').read_text()
    assert all(isinstance(x, str) for x in required_voicemail_auth_checks())
    assert len(required_voicemail_auth_checks()) == 16
