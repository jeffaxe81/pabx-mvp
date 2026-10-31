"""AXE PABX puro: 1.000 números distintos e variantes de mascaramento."""
import pytest
from blocklist import validate_blocklist_number

@pytest.mark.parametrize("case",[pytest.param(i,id=f"AXE-{i+1:05d}") for i in range(1000)])
def test_phone_blocklist_with_1000_distinct_inputs(case):
    number=str(1190000000+case)
    if case<500:
        formats=(number,f"({number[:2]}) {number[2:6]}-{number[6:]}",
                 f"+{number[:2]} {number[2:]}",f" {number} ",
                 f"{number[:2]}.{number[2:6]}.{number[6:]}")
        assert validate_blocklist_number(formats[case%5])==number
    else:
        chars=("\u200b","\u200e","\u202e","\x00","\n")
        index=case%len(number)
        forged=number[:index]+chars[case%5]+number[index:]
        assert validate_blocklist_number(forged) is None
