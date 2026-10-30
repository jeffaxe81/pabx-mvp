from agent_pause import validate_pause_request

def test_pause_denies_malformed_extension():
    for value in ("t1-1001\n", "t1_1001", "t1-1234;foo", "x"*65):
        ok, _, _ = validate_pause_request({"extension":value,"paused":True,"reason":"Almoço"})
        assert not ok

def test_pause_denies_multiline_reason():
    assert not validate_pause_request({"extension":"t1-1001","paused":True,"reason":"Almoço\nInjected"})[0]

def test_good_pause_keeps_existing_contract():
    assert validate_pause_request({"extension":"t1-recepcao","paused":True,"reason":"Almoço"})[0]
