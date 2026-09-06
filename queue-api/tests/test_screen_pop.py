from unittest.mock import patch

from screen_pop import (
    parse_dial_begin_event, build_webhook_payload, dispatch_screen_pop,
)


def test_parses_valid_dial_begin_event():
    event = {
        "Event": "DialBegin", "CallerIDNum": "5511988887777", "CallerIDName": "Cliente Teste",
        "DestExten": "1000", "DestChannel": "PJSIP/t1-recepcao-00000001",
    }
    info = parse_dial_begin_event(event)
    assert info["caller_id_num"] == "5511988887777"
    assert info["caller_id_name"] == "Cliente Teste"
    assert info["destination_exten"] == "1000"


def test_ignores_non_dial_begin_events():
    assert parse_dial_begin_event({"Event": "DialEnd"}) is None
    assert parse_dial_begin_event({"Event": "Hangup"}) is None


def test_ignores_dial_begin_without_caller_id():
    assert parse_dial_begin_event({"Event": "DialBegin"}) is None


def test_build_webhook_payload_structure():
    call_info = {"caller_id_num": "123", "caller_id_name": "Fulano", "destination_exten": "1000"}
    payload = build_webhook_payload(call_info)
    assert payload["event"] == "incoming_call"
    assert payload["caller_number"] == "123"
    assert payload["caller_name"] == "Fulano"
    assert payload["operator_extension"] == "1000"


def test_dispatch_does_nothing_without_webhook_url():
    event = {"Event": "DialBegin", "CallerIDNum": "123"}
    with patch("screen_pop.send_webhook") as mock_send:
        error = dispatch_screen_pop(event, webhook_url="")
    mock_send.assert_not_called()
    assert error is None


def test_dispatch_sends_when_configured_and_event_valid():
    event = {"Event": "DialBegin", "CallerIDNum": "123"}
    with patch("screen_pop.send_webhook") as mock_send:
        error = dispatch_screen_pop(event, webhook_url="https://crm.exemplo.com/webhook")
    mock_send.assert_called_once()
    assert error is None


def test_dispatch_ignores_irrelevant_events_even_with_url_configured():
    event = {"Event": "Hangup"}
    with patch("screen_pop.send_webhook") as mock_send:
        error = dispatch_screen_pop(event, webhook_url="https://crm.exemplo.com/webhook")
    mock_send.assert_not_called()
    assert error is None


def test_dispatch_returns_error_message_on_failure_without_raising():
    event = {"Event": "DialBegin", "CallerIDNum": "123"}
    with patch("screen_pop.send_webhook", side_effect=ConnectionError("crm fora do ar")):
        error = dispatch_screen_pop(event, webhook_url="https://crm.exemplo.com/webhook")
    assert error is not None
    assert "crm fora do ar" in error
