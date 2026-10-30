"""Public import for dynamic-extension publication validators.

The functions live inside conf_generator.py because the SIP lab safely
copies that single generator into its ephemeral isolated test workspace.
This facade retains a stable import surface for API regression tests.
"""
from conf_generator import (
    RULES, inspect_dynamic_extensions, validate_dynamic_extensions,
    MAX_GENERATED_CONF_BYTES,
)
