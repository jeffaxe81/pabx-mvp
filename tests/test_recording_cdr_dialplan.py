"""Contrato de rastreabilidade para chamadas gravadas por tenant."""
from pathlib import Path
import re
from conf_parser import parse_blocks

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


def test_direct_static_calls_attribute_cdr_before_dial_in_each_tenant():
    blocks = {block['name']:block['text'] for block in parse_blocks(ROOT/'asterisk/extensions.conf')}
    for tenant, number in (('t1','1001'), ('t1','1002'), ('t2','1001')):
        route = re.search(r'(?m)^exten\s*=>\s*'+number+r',1,(.*?)(?=^exten\s*=>|\Z)',
                          blocks[tenant+'-internal'],re.S)[1]
        assert route.index('Set(CDR(accountcode)='+tenant+')') < route.index('Dial(PJSIP/'+tenant+'-'+number)
