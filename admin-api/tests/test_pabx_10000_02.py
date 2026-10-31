"""1.000 casos distintos: limpeza de número e alvo de ramal no PABX."""
import pytest
from vip import validate_vip_input

@pytest.mark.parametrize("case", [
    pytest.param(i, id=f"AXE-{i+1001:05d}") for i in range(1000)
])
def test_vip_routing_1000_numbers_and_rejected_extensions(case):
    raw_number=str(1192000000+case)
    valid_target=str(1100+(case%100))
    if case<500:
        normalized_forms=(
            raw_number,
            f"({raw_number[:2]}) {raw_number[2:6]}-{raw_number[6:]}",
            f"+{raw_number[:2]} {raw_number[2:]}",
            f" {raw_number} ",
        )
        submitted=normalized_forms[case%4]
        ok,error,row=validate_vip_input({
            "number":submitted,"target_extension":valid_target})
        assert ok and error is None
        assert row=={"number":raw_number,"target_extension":valid_target}
    else:
        bad_target=valid_target+("x",";Dial","\n","\u200b",":5060")[case%5]
        ok,_,row=validate_vip_input({
            "number":raw_number,"target_extension":bad_target})
        assert not ok and row is None
