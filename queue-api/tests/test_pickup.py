from pickup import validate_pickup_request

CONFIG = {"allowed_extensions": ["t1-recepcao", "t1-recepcao-2"]}


def test_valid_request_for_first_operator():
    ok, error, channel, extension = validate_pickup_request(
        {"channel": "PJSIP/gateway-tdm-0001", "extension": "t1-recepcao"}, CONFIG
    )
    assert ok is True
    assert error is None
    assert channel == "PJSIP/gateway-tdm-0001"
    assert extension == "t1-recepcao"


def test_valid_request_for_second_operator():
    ok, error, channel, extension = validate_pickup_request(
        {"channel": "CH1", "extension": "t1-recepcao-2"}, CONFIG
    )
    assert ok is True
    assert extension == "t1-recepcao-2"


def test_rejects_missing_channel():
    ok, error, channel, extension = validate_pickup_request(
        {"extension": "t1-recepcao"}, CONFIG
    )
    assert ok is False
    assert "channel" in error


def test_rejects_missing_extension():
    ok, error, channel, extension = validate_pickup_request(
        {"channel": "CH1"}, CONFIG
    )
    assert ok is False
    assert "não autorizado" in error


def test_rejects_extension_not_in_allowlist():
    ok, error, channel, extension = validate_pickup_request(
        {"channel": "CH1", "extension": "t1-1001"}, CONFIG
    )
    assert ok is False
    assert "t1-1001" in error


def test_rejects_empty_allowlist():
    ok, error, channel, extension = validate_pickup_request(
        {"channel": "CH1", "extension": "t1-recepcao"}, {"allowed_extensions": []}
    )
    assert ok is False
