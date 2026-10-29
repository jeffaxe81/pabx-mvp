"""Contratos fail-closed da prova de fila em Asterisk real."""
import pytest

from lab.queue_tenant_checks import (
    CASES, inspected_queue_channel, required_queue_runtime_checks,
)
from lab.asterisk_lab import summarize


def line(endpoint="t1-1001", context="t1-internal", extension="1000",
         app="Queue", args="fila-t1,c,,,15"):
    return "PJSIP/" + endpoint + "-00000001!" + context + "!" + extension + "!3!Up!" + app + "!" + args + "!123.1"


def test_accept_only_matching_sip_channel_context_and_exact_queue():
    assert inspected_queue_channel(line(), "t1-1001", "t1") == {
        "exact": True, "no_foreign": True,
    }


@pytest.mark.parametrize("bad", [
    line(context="t2-internal"),
    line(args="fila-t10,c,,,15"),
    line(args="fila-t2,c,,,15"),
    line(args="fila-t1-en,c,,,15"),
    line(app="Dial"),
    line(extension="1001"),
    line(endpoint="t2-1001"),
    line(args="fila-t1-malicious,c,,,15"),
    "",
    "garbage",
])
def test_reject_cross_tenant_or_unrelated_queue_application(bad):
    assert not inspected_queue_channel(bad, "t1-1001", "t1")["exact"]


def test_multiple_matching_channels_must_not_combine_evidence():
    good = line()
    other = line(args="fila-t2,c,,,15").replace("00000001", "00000002")
    assert inspected_queue_channel(good + "\n" + other, "t1-1001", "t1") == {
        "exact": False, "no_foreign": False,
    }


def test_oversized_or_invalid_output_fails_closed():
    for raw in (None, [], "x" * (1024 * 1024 + 1)):
        assert inspected_queue_channel(raw, "t1-1001", "t1") == {
            "exact": False, "no_foreign": False,
        }


def test_gate_requires_all_real_queue_checks():
    from lab.call_checks import required_call_checks
    base = {"real_runtime", "tls_transport", "wss_transport", "container_removed",
            "checkout_clean", "runtime_mounts", "source_label"}
    base.update(f"{key}:{tenant}" for key in (
        "context", "register", "contact", "unregister", "wrong_password"
    ) for tenant in ("t1", "t2", "t3"))
    checks = {key: True for key in base | required_call_checks() | required_queue_runtime_checks()}
    assert len(CASES) == 3
    assert summarize(checks, calls=True, queues=True)["success"]
    assert not summarize(checks, calls=True)["success"]
    assert not summarize({**checks, "queue_exact_tenant:t2": False}, calls=True, queues=True)["success"]
    assert not summarize({**checks, "queue_wait_observed:t2": False}, calls=True, queues=True)["success"]
    assert "queue_wait_observed:t3" in required_queue_runtime_checks()


def test_queues_mode_requires_calls(tmp_path):
    from lab.asterisk_lab import main
    with pytest.raises(SystemExit) as error:
        main(["--queues", "--report", str(tmp_path / "queue-report.json")])
    assert error.value.code != 0
