from ami_protocol import parse_ami_blocks, build_action


def test_parse_single_block():
    raw = "Response: Success\r\nMessage: Authentication accepted\r\n\r\n"
    blocks = parse_ami_blocks(raw)
    assert len(blocks) == 1
    assert blocks[0]["Response"] == "Success"
    assert blocks[0]["Message"] == "Authentication accepted"


def test_parse_multiple_blocks_received_together():
    """
    Na prática, várias mensagens AMI podem chegar juntas num único
    recv() do socket - o parser precisa separar corretamente.
    """
    raw = (
        "Event: QueueCallerJoin\r\nQueue: fila-t1\r\nChannel: PJSIP/t1-9999-0001\r\n\r\n"
        "Event: QueueCallerJoin\r\nQueue: fila-t1\r\nChannel: PJSIP/t1-8888-0002\r\n\r\n"
    )
    blocks = parse_ami_blocks(raw)
    assert len(blocks) == 2
    assert blocks[0]["Channel"] == "PJSIP/t1-9999-0001"
    assert blocks[1]["Channel"] == "PJSIP/t1-8888-0002"


def test_parse_ignores_lines_without_colon():
    raw = "Response: Follows\r\nlinha sem dois pontos\r\nMessage: ok\r\n\r\n"
    blocks = parse_ami_blocks(raw)
    assert blocks[0]["Response"] == "Follows"
    assert blocks[0]["Message"] == "ok"


def test_parse_empty_text_returns_empty_list():
    assert parse_ami_blocks("") == []
    assert parse_ami_blocks("\r\n\r\n") == []


def test_build_action_preserves_field_order_and_terminator():
    action = build_action({"Action": "Login", "Username": "queue-api", "Secret": "x"})
    assert action == "Action: Login\r\nUsername: queue-api\r\nSecret: x\r\n\r\n"


def test_build_action_roundtrip_with_parser():
    """Uma action montada aqui, se 'ecoada', deve dar pra parsear de volta."""
    action = build_action({"Action": "Redirect", "Channel": "PJSIP/abc-0001", "Context": "pickup-target"})
    blocks = parse_ami_blocks(action)
    assert blocks[0]["Action"] == "Redirect"
    assert blocks[0]["Channel"] == "PJSIP/abc-0001"
