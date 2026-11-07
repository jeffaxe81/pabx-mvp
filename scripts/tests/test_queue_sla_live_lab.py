"""Lab de SLA: gate obrigatório de chamada realmente atendida e segura."""
from pathlib import Path

import pytest

from lab.queue_sla_live_checks import (
    _add_private_queue_member, prepare_live_queue_sla, fresh_queue_cdr,
    required_live_queue_sla_checks,
)


def test_stage_only_adds_disposable_member_to_real_queue(tmp_path):
    root = tmp_path / "asterisk"
    (root / "queues_tenants").mkdir(parents=True)
    entries = []
    for t in ("t1", "t2"):
        entries.append(
            f"[fila-{t}]\nstrategy = rrmemory\nmonitor-type = mixmonitor\n"
            f"member => PJSIP/{t}-recepcao\n\n"
            f"[fila-{t}-en]\nstrategy = rrmemory\nmonitor-type = mixmonitor\n"
            f"member => PJSIP/{t}-recepcao\n\n"
        )
    original = "".join(entries)
    (root / "queues.conf").write_text(original, encoding="utf-8")
    t3 = ("[fila-t3]\nstrategy = rrmemory\nmonitor-type = mixmonitor\n"
          "member => PJSIP/t3-recepcao\n\n"
          "[fila-t3-en]\nstrategy = rrmemory\nmonitor-type = mixmonitor\n"
          "member => PJSIP/t3-recepcao\n")
    (root / "queues_tenants/t3.conf").write_text(t3, encoding="utf-8")
    prepared = {"conf": root}
    prepare_live_queue_sla(prepared)
    assert prepared["live_queue_sla_staged"] is True
    assert prepared["members_ami_username"] == "axe-members-lab"
    assert len(prepared["members_ami_secret"]) == 64
    manager = (root / "manager.conf").read_text(encoding="utf-8")
    assert "bindaddr=127.0.0.1" in manager
    assert "permit=127.0.0.1/255.255.255.255" in manager
    for t in ("t1", "t2", "t3"):
        file = root / ("queues.conf" if t != "t3" else "queues_tenants/t3.conf")
        actual = file.read_text(encoding="utf-8")
        assert actual.count("member => PJSIP/" + t + "-1002") == 1
        assert actual.count("monitor-type = mixmonitor") >= 1
        assert file.stat().st_mode & 0o077 == 0
    assert (root / "queues.conf").read_text().replace(
        "member => PJSIP/t1-1002\n", ""
    ).replace("member => PJSIP/t2-1002\n", "") == original
    assert (root / "queues_tenants/t3.conf").read_text().replace(
        "member => PJSIP/t3-1002\n", "") == t3
    with pytest.raises(ValueError):
        prepare_live_queue_sla(prepared)


def test_refuse_queue_stage_without_real_mixmonitor_and_correct_tenant(tmp_path):
    file = tmp_path / "queues.conf"
    for body in (
        "[fila-t1]\nstrategy = rrmemory\n",
        "[fila-t1]\nmonitor-type = mixmonitor\n",
        "[fila-t10]\nstrategy = rrmemory\nmonitor-type = mixmonitor\n",
        "[fila-t1]\nstrategy = rrmemory\nmonitor-type = mixmonitor\n"
        "member => PJSIP/t1-1002\n",
    ):
        file.write_text(body, encoding="utf-8")
        with pytest.raises(ValueError):
            _add_private_queue_member(file, "t1")


@pytest.mark.parametrize("tenant", ("t1", "t2", "t3"))
def test_cdr_is_from_same_fresh_answered_queue_call(tenant):
    raw = (f'"{tenant}","1001","1000","{tenant}-internal",'
           f'"PJSIP/{tenant}-1001-0000001a",'
           f'"PJSIP/{tenant}-1002-0000001b",'
           '"ANSWERED","3","1792670400.123"\n')
    assert fresh_queue_cdr(raw, {"1792670400.111"}, tenant, "1792670400.123")
    assert not fresh_queue_cdr(raw, {"1792670400.123"}, tenant, "1792670400.123")
    assert not fresh_queue_cdr(raw + raw, set(), tenant, "1792670400.123")
    for modified in (
        raw.replace('"ANSWERED"', '"NO ANSWER"'),
        raw.replace(',"3",', ',"0",'),
        raw.replace('"1000"', '"1010"'),
        raw.replace(tenant + "-internal", "t10-internal"),
        raw.replace(tenant + "-1002-", "t10-1002-"),
    ):
        assert not fresh_queue_cdr(modified, set(), tenant, "1792670400.123")


def test_new_gate_cannot_be_skipped_by_summary():
    from lab.asterisk_lab import summarize
    from lab.call_checks import required_call_checks
    from lab.queue_sla_live_checks import required_live_queue_sla_checks
    base = {
        "real_runtime", "tls_transport", "wss_transport", "container_removed",
        "checkout_clean", "runtime_mounts", "source_label",
    }
    base.update(
        name + ":" + tenant for tenant in ("t1", "t2", "t3")
        for name in ("context", "register", "contact",
                     "unregister", "wrong_password")
    )
    base |= required_call_checks() | required_live_queue_sla_checks()
    assert len(required_live_queue_sla_checks()) == 35
    assert summarize({key: True for key in base},
                     calls=True, queue_sla=True)["success"]
    base.remove("sla_live_agentconnect_real:t2")
    assert not summarize({key: True for key in base},
                         calls=True, queue_sla=True)["success"]
