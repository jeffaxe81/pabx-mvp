"""Contratos do aceite real de MixMonitor, CDR e HTTP por tenant."""
import wave

import pytest

from lab import recording_checks as recording


def test_cdr_export_preserves_same_row_evidence_and_start_timestamp():
    raw = ('"t2","1101","1102","t2-internal","PJSIP/t2-1101-a",'
           '"PJSIP/t2-1102-b","ANSWERED","2","1793210400.11",'
           '"2026-10-28 10:00:00"\n')
    assert recording.recording_cdr_events(raw) == [{
        'Event': 'Cdr', 'AccountCode': 't2', 'CallerIDNum': '1101',
        'Destination': '1102', 'DestinationContext': 't2-internal',
        'Channel': 'PJSIP/t2-1101-a', 'DestinationChannel': 'PJSIP/t2-1102-b',
        'Disposition': 'ANSWERED', 'BillableSeconds': '2',
        'UniqueID': '1793210400.11', 'StartTime': '2026-10-28 10:00:00',
    }]


@pytest.mark.parametrize('raw', ['', '"unterminated', 'a,b\n', 'x' * (1024*1024+1)])
def test_invalid_cdr_export_fails_closed(raw):
    with pytest.raises(ValueError):
        recording.recording_cdr_events(raw)


def test_wav_evidence_requires_actual_non_silent_audio_frames(tmp_path):
    audio = tmp_path / 'synthetic.wav'
    with wave.open(str(audio), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes(b'\x00\x01' * 8000)
    assert recording.recorded_audio_valid(audio)
    with wave.open(str(audio), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes(b'\x00\x00' * 8000)
    assert not recording.recorded_audio_valid(audio)
    audio.write_bytes(b'RIFF bogus header')
    assert not recording.recorded_audio_valid(audio)


@pytest.mark.skipif(__import__('os').name == 'nt', reason='production openat/fcntl require Linux')
@pytest.mark.parametrize('tenants', [('t2',), ('t1', 't2', 't3', 't10')])
def test_real_http_catalog_import_authorization_and_hot_revocation(tmp_path, tenants):
    root = __import__('pathlib').Path(__file__).resolve().parents[2]
    audio_dir = tmp_path / 'audio'
    audio_dir.mkdir()
    rows = []
    for index, tenant in enumerate(tenants):
        filename = f'20261028-10000{index}-1101-1102.wav'
        audio = audio_dir / filename
        with wave.open(str(audio), 'wb') as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(8000)
            output.writeframes(b'\x00\x01' * 8000)
        rows.append({'filename': filename, 'tenant': tenant, 'owner_extension': tenant+'-1102',
                     'source_ref': 'CDR:1793210400.'+str(index+11)})
    results = recording.exercise_recording_http(root, tmp_path, audio_dir, rows)
    for tenant in tenants:
        assert results[tenant] == {
            'catalog_applied': True, 'http_owner_list': True, 'http_owner_audio': True,
            'http_supervisor': True, 'http_admin': True, 'http_other_agent': True,
            'http_cross_tenant': True, 'http_anonymous': True,
            'http_bad_origin': True, 'http_revoked': True,
        }
