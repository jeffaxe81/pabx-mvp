from quality_monitoring import is_poor_quality

def test_high_rtt_triggers_quality_warning():
    assert is_poor_quality({"jitter_ms":2,"packet_loss_percent":0.2,"rtt_ms":550})
    assert not is_poor_quality({"jitter_ms":2,"packet_loss_percent":0.2,"rtt_ms":200})

def test_untrusted_rtt_and_threshold_are_ignored_conservatively():
    assert not is_poor_quality({"rtt_ms":float("nan")})
    assert not is_poor_quality({"rtt_ms":1000}, rtt_threshold_ms=float("inf"))
    assert not is_poor_quality({"rtt_ms":1000}, rtt_threshold_ms=True)
