import pytest
from ami_protocol import build_action


def test_rejects_crlf_in_field_values():
    with pytest.raises(ValueError):
        build_action({"Action": "DBPut", "Key": "1001\\r\\nAction: Command".replace("\\r", "\r").replace("\\n", "\n")})


def test_rejects_field_name_injection():
    with pytest.raises(ValueError):
        build_action({"Action\nCommand": "Originate"})


def test_valid_ami_action_unchanged():
    assert build_action({"Action": "Ping"}) == "Action: Ping\r\n\r\n"
