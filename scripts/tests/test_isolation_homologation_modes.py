"""Every real homologation mode needs its own complete, explicit gate."""
import pytest

from lab.asterisk_lab import main, summarize
from lab.call_checks import required_call_checks
from lab.recording_checks import required_recording_checks
from lab.voicemail_auth_runtime import required_voicemail_auth_checks


def base_checks():
    checks = {"real_runtime", "tls_transport", "wss_transport", "container_removed",
              "checkout_clean", "runtime_mounts", "source_label"}
    checks |= {f"{key}:{tenant}" for key in (
        "context", "register", "contact", "unregister", "wrong_password"
    ) for tenant in ("t1", "t2", "t3")}
    return checks | required_call_checks()


@pytest.mark.parametrize("mode,required", (
    ("recordings", required_recording_checks),
    ("voicemail_auth", required_voicemail_auth_checks),
))
def test_extended_gate_rejects_missing_false_or_unrequested_evidence(mode, required):
    checks = {key: True for key in base_checks() | required()}
    options = {"calls": True, mode: True}
    assert summarize(checks, **options)["success"]
    assert not summarize(checks, calls=True)["success"]
    missing = next(iter(required()))
    assert not summarize({key: val for key, val in checks.items() if key != missing},
                         **options)["success"]
    assert not summarize({**checks, missing: False}, **options)["success"]


@pytest.mark.parametrize("mode", ("--recordings", "--voicemail-auth"))
def test_extended_homologation_requires_calls_before_starting_runtime(mode, tmp_path, capsys):
    with pytest.raises(SystemExit) as error:
        main([mode, "--report", str(tmp_path / "report.json")])
    assert error.value.code != 0
    assert "requerem --calls" in capsys.readouterr().err
    assert not (tmp_path / "report.json").exists()
