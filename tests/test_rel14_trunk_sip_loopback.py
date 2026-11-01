"""REL-14: validações da sonda SIP restrita ao loopback."""
import socket
import time

from lab.trunk_sip_loopback_checks import (
    CASES, LoopbackTrunk, parse_invite_target, required_trunk_checks,
)


def test_gates_rel14_exigem_cada_caso_sem_atribuir_producao():
    assert len(CASES) == 9
    assert len({c[0] for c in CASES}) == len(CASES)
    assert len(required_trunk_checks()) == 12
    assert {"trunk:t1-primary", "trunk:t1-secondary", "trunk:t2-primary",
            "trunk:t1-international-deny", "trunk:t1-secondary-blocklist"} <= required_trunk_checks()
    assert all(c[6] in ("primary", "secondary", None) for c in CASES)


def test_parser_rejeita_uri_externo_metodo_errado_e_valor_extra():
    port = 32011
    assert parse_invite_target(b"INVITE sip:1198765432@127.0.0.1:32011 SIP/2.0\r\n", port) == "1198765432"
    assert parse_invite_target(b"INVITE sip:1198765432@192.168.1.200:32011 SIP/2.0\r\n", port) == "invalid-uri"
    assert parse_invite_target(b"OPTIONS sip:1198765432@127.0.0.1:32011 SIP/2.0\r\n", port) == "invalid-uri"
    assert parse_invite_target(b"INVITE sip:1234@127.0.0.1:32012 SIP/2.0\r\n", port) == "invalid-uri"
    assert parse_invite_target(b"INVITE sip:abc@127.0.0.1:32011 SIP/2.0\r\n", port) == "invalid-uri"


def test_tronco_responde_486_e_registra_apenas_destino_sintetico():
    sink = LoopbackTrunk("primary")
    sink.start()
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.bind(("127.0.0.1", 0))
    client.settimeout(2)
    try:
        payload = ("\r\n".join([
            f"INVITE sip:1198765432@127.0.0.1:{sink.port} SIP/2.0",
            "Via: SIP/2.0/UDP 127.0.0.1:54321;branch=z9hG4bKrel14",
            "From: <sip:1001@localhost>;tag=abc",
            "To: <sip:1198765432@localhost>",
            "Call-ID: synthetic-rel14@localhost",
            "CSeq: 1 INVITE",
            "Content-Length: 0",
            "", "",
        ])).encode("ascii")
        client.sendto(payload, ("127.0.0.1", sink.port))
        answer, _ = client.recvfrom(4096)
        assert answer.startswith(b"SIP/2.0 486 Busy Here\r\n")
        assert b"CSeq: 1 INVITE\r\n" in answer
        deadline = time.monotonic() + 1
        while not sink.events and time.monotonic() < deadline:
            time.sleep(.01)
        assert sink.events == ["1198765432"]
    finally:
        client.close()
        sink.close()
