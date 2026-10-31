from pickup import validate_pickup_request

def test_pickup_rejects_string_allowlist_as_substring():
    assert not validate_pickup_request(
        {"channel":"CH1","extension":"t1-recepcao"},
        {"allowed_extensions":"t1-recepcao,t2-recepcao"})[0]

def test_pickup_rejects_ambiguous_space_in_channel_or_extension():
    cfg = {"allowed_extensions":["t1-recepcao", "t1 recepcao"]}
    for channel in ("CH 1", " CH1", "CH1 "):
        assert not validate_pickup_request({"channel":channel,"extension":"t1-recepcao"},cfg)[0]
    assert not validate_pickup_request({"channel":"CH1","extension":"t1 recepcao"},cfg)[0]
    assert validate_pickup_request({"channel":"CH1","extension":"t1-recepcao"},cfg)[0]
