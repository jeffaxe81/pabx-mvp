"""100-test cycle 51–60: Asterisk Manager protocol and reload failures."""
import pytest
from ami_protocol import build_action,parse_ami_blocks
from ami_reload_policy import cli_reload_output_failed

def test_051_ami_action_has_double_crlf_terminator():
    raw=build_action({"Action":"Ping"})
    assert raw=="Action: Ping\r\n\r\n"

def test_052_ami_action_preserves_header_order():
    raw=build_action({"Action":"Login","Username":"axe","Secret":"opaque"})
    assert raw.split("\r\n")[:3]==["Action: Login","Username: axe","Secret: opaque"]

def test_053_ami_parser_splits_responses():
    raw="Response: Success\r\n\r\nResponse: Error\r\nMessage: Denied\r\n\r\n"
    result=parse_ami_blocks(raw)
    assert [r["Response"] for r in result]==["Success","Error"]

def test_054_ami_parser_ignores_malformed_line():
    assert parse_ami_blocks("Response: Success\r\nMalformatted\r\n\r\n")[0]=={"Response":"Success"}

def test_055_ami_rejects_empty_fields():
    for bad in ({},None,[]):
        with pytest.raises(ValueError):
            build_action(bad)

def test_056_ami_rejects_injected_field_name():
    with pytest.raises(ValueError):
        build_action({"Action\r\nSecret":"Ping"})

def test_057_ami_rejects_colon_in_header_name():
    with pytest.raises(ValueError):
        build_action({"Action:Fake":"Ping"})

def test_058_ami_rejects_multiline_field_value():
    with pytest.raises(ValueError):
        build_action({"Action":"Ping\r\nAction: Originate"})

def test_059_ami_reload_detects_explicit_failures():
    for raw in ("No such command 'pjsip reload'","Invalid command","Cannot reload pjsip",
                "Error: reload failed","CLI command failed"):
        assert cli_reload_output_failed(raw)

def test_060_ami_reload_does_not_flag_informative_zero_error():
    for raw in ("Reloaded successfully\n0 errors","Module loaded","0 errors; 0 warnings"):
        assert not cli_reload_output_failed(raw)
