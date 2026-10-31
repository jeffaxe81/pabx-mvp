import pytest
from ami_protocol import build_action

def test_queue_ami_refuses_header_control_and_ambiguous_names():
    for name in (" Action", "Action ", "A\tB", "A\x00B", "A"*65, "A:B"):
        with pytest.raises(ValueError):
            build_action({name: "Ping"})
    assert build_action({"Action":"Ping"}) == "Action: Ping\r\n\r\n"
