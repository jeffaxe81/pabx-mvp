from ami_reload_policy import cli_reload_output_failed

def test_admin_reload_detects_explicit_cli_error_prefix():
    for raw in ("Error: invalid module", "CLI command failed to reload", "\nError: internal failure\n"):
        assert cli_reload_output_failed(raw)
    for raw in ("Reload successful", "0 errors detected", "Module loaded correctly"):
        assert not cli_reload_output_failed(raw)
