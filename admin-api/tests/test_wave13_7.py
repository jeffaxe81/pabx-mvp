from ami_reload_policy import cli_reload_output_failed

def test_reload_cli_rejects_new_explicit_failure_lines():
    assert cli_reload_output_failed("Invalid command: module reload")
    assert cli_reload_output_failed("Cannot reload module pjsip")
    assert cli_reload_output_failed("Cannot load module foo")
    assert not cli_reload_output_failed("0 errors; module loaded")
