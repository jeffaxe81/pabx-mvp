from ami_reload_policy import cli_reload_output_failed

def test_reload_detects_explicit_command_failures():
    for output in ("Error executing command: reload", "Module chan_pjsip reload failed", "  ERROR EXECUTING COMMAND"):
        assert cli_reload_output_failed(output)

def test_reload_preserves_informational_success_output():
    for output in ("Reload complete. 0 errors.", "No errors were detected.", "", "PJSIP configuration reloaded."):
        assert not cli_reload_output_failed(output)
