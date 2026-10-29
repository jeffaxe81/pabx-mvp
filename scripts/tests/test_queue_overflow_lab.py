"""Contrato de timeout e transbordo: mesmo canal, fila correta, sem loops."""
import pytest

from lab.queue_overflow_checks import (
    EXTENSION, TENANTS, active_queue, overflow_stanza, overflow_cdr_matches,
    prepare_queue_overflow, required_queue_overflow_checks,
)


def test_staging_adds_only_entry_point_for_all_three_tenants(tmp_path):
    root = tmp_path / "asterisk"
    (root / "extensions_tenants").mkdir(parents=True)
    baseline = []
    for tenant in ("t1", "t2"):
        baseline.append(
            f"[{tenant}-internal]\n"
            "exten => 1000,1,Answer()\n"
            " same => n,Queue(fila,c,,,2)\n"
            " same => n,GotoIf(TIMEOUT?fila-overflow,1)\n"
            " same => n,Set(FILA_OVERFLOW=fila-geral)\n"
            "exten => fila-overflow,1,NoOp(timeout)\n"
            "exten => fazer-overflow,1,Goto(1000,1)\n\n"
        )
    original = "".join(baseline)
    (root / "extensions.conf").write_text(original, encoding="utf-8")
    generated = ("[t3-internal]\n"
                 "exten => 1000,1,Answer()\n"
                 " same => n,Queue(fila,c,,,2)\n"
                 " same => n,GotoIf(TIMEOUT?fila-overflow,1)\n"
                 " same => n,Set(FILA_OVERFLOW=fila-geral)\n"
                 "exten => fila-overflow,1,NoOp(timeout)\n"
                 "exten => fazer-overflow,1,Goto(1000,1)\n")
    (root / "extensions_tenants/t3.conf").write_text(generated, encoding="utf-8")
    prepared = {"conf": root}
    prepare_queue_overflow(prepared)
    assert prepared["lab_overflow_routes_staged"] is True
    for tenant in TENANTS:
        path = root / ("extensions.conf" if tenant != "t3" else "extensions_tenants/t3.conf")
        staged = path.read_text(encoding="utf-8")
        assert staged.count(overflow_stanza(tenant)) == 1
        assert f"exten => {EXTENSION},1,Set(FILA_IDIOMA=fila-{tenant}-en)" in staged
        assert staged.index(overflow_stanza(tenant)) > staged.index(f"[{tenant}-internal]")
        assert staged.count("Queue(fila,c,,,2)") >= 1
        assert path.stat().st_mode & 0o077 == 0
    assert (root / "extensions.conf").read_text().replace(
        overflow_stanza("t1"), ""
    ).replace(overflow_stanza("t2"), "") == original
    assert (root / "extensions_tenants/t3.conf").read_text().replace(
        overflow_stanza("t3"), ""
    ) == generated
    with pytest.raises(ValueError, match="duplicada"):
        prepare_queue_overflow(prepared)


def test_same_line_queue_inspector_rejects_cross_tenant_and_ambiguity():
    def line(channel, context, extension, queue, *, app="Queue", state="Up"):
        return "!".join((channel, context, extension, "1", state,
                         app, queue + ",c,,,2", ""))
    t1 = "PJSIP/t1-1001-0000001a"
    expected = line(t1, "t1-internal", "1000", "fila-t1-en")
    assert active_queue(expected, "t1-1001", "t1") == (t1, "fila-t1-en")
    assert active_queue(line(t1, "t1-internal", "1000", "fila-t1"),
                        "t1-1001", "t1") == (t1, "fila-t1")
    for raw in (expected + "\n" + expected,
                line(t1, "t10-internal", "1000", "fila-t1-en"),
                line(t1, "t1-internal", "9987", "fila-t1-en"),
                line(t1, "t1-internal", "1000", "fila-t10-en"),
                line(t1, "t1-internal", "1000", "fila-t1-en", app="Dial"),
                line(t1, "t1-internal", "1000", "fila-t1-en", state="Ring")):
        assert active_queue(raw, "t1-1001", "t1") is None
    assert active_queue(expected, "t10-1001", "t10") is None


@pytest.mark.parametrize("tenant", TENANTS)
def test_cdr_cannot_borrow_account_or_channel_from_other_tenant(tenant):
    row = (f"{tenant},1001,9987,{tenant}-internal,"
           f"PJSIP/{tenant}-1001-0000001a,,ANSWERED,4,1792670400.123\n")
    assert overflow_cdr_matches(row, tenant)
    assert not overflow_cdr_matches(row, next(t for t in TENANTS if t != tenant))
    assert not overflow_cdr_matches(row + row, tenant)
    for broken in ("ANSWERED", "9987", f"{tenant}-internal",
                   f"PJSIP/{tenant}-1001", ",4,"):
        alternate = ("BUSY" if broken == "ANSWERED" else "1010" if broken == "9987"
                     else "t10-internal" if broken.endswith("-internal")
                     else "PJSIP/t10-1001" if broken.startswith("PJSIP/")
                     else ",0,")
        assert not overflow_cdr_matches(row.replace(broken, alternate), tenant)


def test_lab_queue_overflow_cannot_be_skipped_in_real_runtime_checklist():
    required = required_queue_overflow_checks()
    assert len(required) == 33
    assert "overflow_general_queue:t3" in required
    assert "overflow_same_channel:t2" in required
    assert "overflow_no_loop:t1" in required
    assert overflow_stanza("t1").count("Goto(1000,1)") == 1
    with pytest.raises(ValueError):
        overflow_stanza("t10")
