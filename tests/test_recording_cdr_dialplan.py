"""Contrato de rastreabilidade para chamadas gravadas por tenant."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_all_explicit_static_mixmonitors_have_accountcode_before_recording():
    source = (ROOT / "asterisk" / "extensions.conf").read_text()
    lines = source.splitlines()
    count = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("same => n,MixMonitor("):
            count += 1
            assert lines[i - 1].strip().startswith("same => n,Set(CDR(accountcode)=t")
    assert count == 8


def test_static_queue_entries_receive_tenant_accountcode():
    source = (ROOT / "asterisk" / "extensions.conf").read_text()
    assert source.count("same => n,Set(CDR(accountcode)=t1)") >= 1
    assert source.count("same => n,Set(CDR(accountcode)=t2)") >= 1
    assert source.count("same => n,Queue(") >= 2
