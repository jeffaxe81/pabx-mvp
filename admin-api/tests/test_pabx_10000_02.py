"""AXE PABX puro: 1.000 telefones e destinos SIP sujeitos à validação."""
import pytest
from vip import validate_vip_input

@pytest.mark.parametrize("case",[pytest.param(i,id=f"AXE-{i+1001:05d}") for i in range(1000)])
def test_direct_routing_1000_unique_caller_id_and_destination_pairs(case):
    number=str(1192000000+case)
    target=str(1100+case%100)
    if case<500:
        forms=(number,f"({number[:2]}) {number[2:6]}-{number[6:]}",
               f"+{number[:2]} {number[2:]}",f" {number} ")
        ok,error,row=validate_vip_input({"number":forms[case%4],"target_extension":target})
        assert ok and error is None and row=={"number":number,"target_extension":target}
    else:
        bad=(target+"x",target+";Dial",
             target[:2]+"\n"+target[2:],target[:2]+"\u200b"+target[2:],
             target+":5060")[case%5]
        ok,error,row=validate_vip_input({"number":number,"target_extension":bad})
        assert not ok and row is None
