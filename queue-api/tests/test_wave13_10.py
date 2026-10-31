import pytest
from unittest.mock import patch
from screen_pop import send_webhook

def test_crm_webhook_rejects_invalid_timeout_without_network():
    for timeout in (0, -1, 31, None, True, "5", []):
        with patch("screen_pop.urllib.request.urlopen") as net:
            with pytest.raises(ValueError):
                send_webhook("https://crm.example/webhook", {"event":"incoming_call"}, timeout=timeout)
            net.assert_not_called()
