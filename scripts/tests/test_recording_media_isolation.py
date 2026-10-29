"""A valid WAV from another tenant cannot satisfy recording acceptance."""
import math
import struct
import wave

import pytest

from lab.recording_checks import recorded_audio_tenant, tenant_tone


def write_tone(path, frequency):
    with wave.open(str(path), 'wb') as audio:
        audio.setparams((1, 2, 8000, 0, 'NONE', 'synthetic'))
        audio.writeframes(b''.join(struct.pack('<h', round(8000*math.sin(
            2*math.pi*frequency*i/8000))) for i in range(8000)))


@pytest.mark.parametrize('tenant,frequency', [('t1', 500), ('t2', 1000),
                                             ('t3', 1500), ('t10', 2000)])
def test_recording_requires_its_tenant_marker_and_rejects_foreign_wav(tmp_path, tenant, frequency):
    audio = tmp_path/'recording.wav'
    write_tone(audio, frequency)
    assert recorded_audio_tenant(audio, tenant)
    foreign = 2000 if frequency != 2000 else 500
    write_tone(audio, foreign)
    assert not recorded_audio_tenant(audio, tenant)
    write_tone(audio, 0)
    assert not recorded_audio_tenant(audio, tenant)


def test_tenant_payloads_are_distinct_fixed_size_pcmu_and_unknown_scope_fails():
    assert len({tenant_tone(t) for t in ('t1', 't2', 't3', 't10')}) == 4
    assert all(len(tenant_tone(t)) == 160 for t in ('t1', 't2', 't3', 't10'))
    with pytest.raises(ValueError):
        tenant_tone('t11')


def test_real_srtp_exchange_accepts_distinct_controlled_payloads():
    from lab.srtp_media import SrtpMedia, exchange
    left, right = SrtpMedia(), SrtpMedia()
    try:
        left.negotiate(right.offer())
        right.negotiate(left.offer())
        result = exchange(left, right, duration=.3,
                          tones=(tenant_tone('t1'), tenant_tone('t10')))
        assert result['payloads_match'] and result['authenticated']
        assert result['tamper_rejected'] and result['replay_rejected']
    finally:
        left.close()
        right.close()
