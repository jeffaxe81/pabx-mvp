"""Regressão para payloads HTTP malformados e JSON administrativo grande."""
import io
import json
from email.message import Message
from types import SimpleNamespace

import pytest

from server import Handler, MAX_JSON_BODY_BYTES


def decode(payload, length=None, transfer=None, extra_lengths=()):
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    headers = Message()
    if length is not None:
        headers.add_header("Content-Length", str(length))
    if transfer is not None:
        headers.add_header("Transfer-Encoding", transfer)
    for another in extra_lengths:
        headers.add_header("Content-Length", str(another))
    instance = SimpleNamespace(
        headers=headers, rfile=io.BytesIO(payload), close_connection=False
    )
    result = Handler._read_json_body(instance)
    return result, instance


def test_valid_json_object_and_unicode_are_accepted():
    payload = json.dumps({"tenant": "t3", "nome": "São Paulo"}, ensure_ascii=False)
    result, handler = decode(payload, length=len(payload.encode("utf-8")))
    assert result == {"tenant": "t3", "nome": "São Paulo"}
    assert not handler.close_connection


def test_missing_content_length_preserves_empty_body_compatibility():
    result, handler = decode(b"")
    assert result == {}
    assert not handler.close_connection


@pytest.mark.parametrize("body", [b"[]", b"null", b"true", b"123", b'"string"'])
def test_nonobject_json_is_rejected(body):
    result, handler = decode(body, length=len(body))
    assert result is None
    assert handler.close_connection


@pytest.mark.parametrize("length", ["-1", "x", "1.0", "+2", " 2", "9\n8"])
def test_ambiguous_or_invalid_content_length_is_rejected(length):
    result, handler = decode(b"{}", length=length)
    assert result is None
    assert handler.close_connection


def test_duplicated_content_length_rejected_even_when_equal():
    result, handler = decode(b"{}", length=2, extra_lengths=[2])
    assert result is None
    assert handler.close_connection


def test_chunked_transfer_encoding_rejected_even_with_length():
    result, handler = decode(b"{}", length=2, transfer="chunked")
    assert result is None
    assert handler.close_connection


def test_too_large_content_length_rejected_without_reading_body():
    class MustNotRead:
        def read(self, length):
            raise AssertionError("body must not be read")
    headers = Message()
    headers.add_header("Content-Length", str(MAX_JSON_BODY_BYTES + 1))
    handler = SimpleNamespace(
        headers=headers, rfile=MustNotRead(), close_connection=False
    )
    assert Handler._read_json_body(handler) is None
    assert handler.close_connection


def test_maximum_allowed_size_is_accepted():
    prefix = len(b'{"text":""}')
    data = b'{"text":"' + b"x" * (MAX_JSON_BODY_BYTES - prefix) + b'"}'
    assert len(data) == MAX_JSON_BODY_BYTES
    result, handler = decode(data, length=len(data))
    assert len(result["text"]) == MAX_JSON_BODY_BYTES - prefix
    assert not handler.close_connection


def test_truncated_body_and_malformed_json_are_rejected():
    for body, length in ((b'{"name":"abc"}', 50), (b'{bad', 4)):
        result, handler = decode(body, length=length)
        assert result is None
        assert handler.close_connection


def test_non_utf8_json_is_rejected():
    result, handler = decode(b'{"nome":"\xff"}', length=12)
    assert result is None
    assert handler.close_connection
