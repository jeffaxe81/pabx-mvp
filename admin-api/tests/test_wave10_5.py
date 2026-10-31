from sounds import is_safe_sound_filename

def test_sound_filename_rejects_non_string_without_crash():
    for raw in (True, 123, [], {}, ["audio.wav"], b"audio.wav"):
        assert is_safe_sound_filename(raw) is False

def test_sound_filename_must_match_completely():
    assert not is_safe_sound_filename("audio.wav\n")
    assert not is_safe_sound_filename("audio.wav/../")
    assert is_safe_sound_filename("audio-01.wav")
