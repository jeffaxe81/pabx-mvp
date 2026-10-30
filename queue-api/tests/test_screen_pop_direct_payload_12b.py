import pytest
from screen_pop import build_webhook_payload

def test_direct_payload_rejects_bad_number():
    for n in ("123\n456", "1"*65, "", " "):
        with pytest.raises(ValueError):
            build_webhook_payload({"caller_id_num": n})

def test_direct_payload_drops_unsafe_optional_fields():
    data = build_webhook_payload({"caller_id_num":"123","caller_id_name":"x\nInjected","destination_exten":["1010"]})
    assert data["caller_number"] == "123"
    assert data["caller_name"] == ""
    assert data["operator_extension"] == ""
