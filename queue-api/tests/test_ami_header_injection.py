import pytest
from ami_protocol import build_action


def test_rejects_newlines_in_values():
    with pytest.raises(ValueError):
        build_action({"Action": "Originate", "CallerID": "Cliente\r\nAction: Command"})


def test_rejects_colon_in_key():
    with pytest.raises(ValueError):
        build_action({"Action: Malicious": "Ping"})


def test_valid_action():
    assert build_action({"Action": "Ping"}) == "Action: Ping\r\n\r\n"
