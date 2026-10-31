"""AXE PABX puro: 1.000 mensagens AMI válidas ou com injeção CRLF."""
import pytest
from ami_protocol import build_action,parse_ami_blocks

@pytest.mark.parametrize("case",[pytest.param(i,id=f"AXE-{i+5001:05d}") for i in range(1000)])
def test_ami_framing_and_header_injection_with_1000_messages(case):
    username=f"tenant-admin-{case:04d}"
    if case<500:
        action=build_action({"Action":"Login","Username":username,
                             "ActionID":f"axe-{case:06d}"})
        assert action.endswith("\r\n\r\n") and action.count("Action:")==1
        blocks=parse_ami_blocks(action)
        assert len(blocks)==1 and blocks[0]=={
            "Action":"Login","Username":username,"ActionID":f"axe-{case:06d}"}
    else:
        injected=(f"{username}\r\nAction: Originate"
                  if case%2 else f"{username}\nSecret: leak-{case}")
        with pytest.raises(ValueError):
            build_action({"Action":"Login","Username":injected})
