import pytest
from screen_pop import parse_dial_begin_event, build_webhook_payload

def test_screen_pop_requires_telephone_digits_not_free_text():
    for number in ("customer 123", "anonymous", "123 456", "123-456",
                   "123\nforged", "+", "1"*21):
        assert parse_dial_begin_event({"Event":"DialBegin","CallerIDNum":number}) is None
        with pytest.raises(ValueError):
            build_webhook_payload({"caller_id_num":number})
    assert parse_dial_begin_event({"Event":"DialBegin","CallerIDNum":"+5511999999999"})["caller_id_num"]=="+5511999999999"
