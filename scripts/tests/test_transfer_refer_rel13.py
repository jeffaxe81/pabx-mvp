"""REL-13: regressão do emissor REFER e limites do laboratório."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lab.sip_calls import CallPeer, Dialog


class RecordingSocket:
    def __init__(self):
        self.wires = []
    def sendall(self, data):
        self.wires.append(data)


def peer(fake_code=202):
    client = CallPeer.__new__(CallPeer)
    client.username = "t1-1002"
    client.port = 50123
    client.target_port = 5061
    client.connection = RecordingSocket()
    client.events = []
    client.final_response = (
        lambda dialog, method, branch: (
            fake_code, {"to": [dialog.remote]}, b""
        )
    )
    return client


def dialogue():
    return Dialog("sintetico@localhost",
                  "<sip:t1-1002@localhost>;tag=local1",
                  "<sip:asterisk@localhost>;tag=remote1",
                  "sip:asterisk@127.0.0.1:5061;transport=tls", 2)


def test_refer_restringe_destino_e_preserva_dialogo():
    client, dialog = peer(), dialogue()
    assert client.blind_transfer(dialog, "1003") == 202
    wire = client.connection.wires[0].decode("ascii")
    assert wire.startswith("REFER sip:asterisk@127.0.0.1:5061;transport=tls SIP/2.0\r\n")
    assert "\r\nRefer-To: <sip:1003@127.0.0.1:5061;transport=tls>\r\n" in wire
    assert "\r\nCall-ID: sintetico@localhost\r\n" in wire
    assert "\r\nCSeq: 3 REFER\r\n" in wire
    assert client.events == ["refer_sent", "refer_accepted"]


@pytest.mark.parametrize("number", ["", "1003\r\nEvil: yes", "t2-1001",
                                    "001198765432", "../../1003", 1003])
def test_refer_rejeita_destinos_fora_do_escopo(number):
    client = peer()
    with pytest.raises(ValueError):
        client.blind_transfer(dialogue(), number)
    assert client.connection.wires == []


def test_refer_nao_conta_erro_sip_como_transferencia():
    from lab.sip_calls import CallRejected
    client = peer(403)
    with pytest.raises(CallRejected) as rejected:
        client.blind_transfer(dialogue(), "1003")
    assert rejected.value.code == 403
    assert "refer_accepted" not in client.events


def test_refer_rejeita_peer_de_outro_perfil_e_uri_externa():
    client = peer()
    client.username = "gateway-tdm"
    with pytest.raises(ValueError):
        client.blind_transfer(dialogue(), "1003")
    assert client.connection.wires == []
    client.username = "t1-1002"
    dialog = dialogue()
    dialog.uri = "sip:asterisk@192.0.2.21:5060"
    with pytest.raises(ValueError):
        client.blind_transfer(dialog, "1003")
    assert client.connection.wires == []


def test_gates_rel13_exigem_cada_prova_para_dois_tenants():
    from lab.transfer_checks import required_transfer_checks
    checks = required_transfer_checks()
    assert len(checks) == 12
    assert "refer_202:t1" in checks
    assert "target_answer:t2" in checks
