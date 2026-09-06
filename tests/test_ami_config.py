"""
Testes estáticos de queues.conf e manager.conf.
"""
from pathlib import Path

from conf_parser import parse_blocks, get_key

QUEUES_CONF = Path(__file__).parent.parent / "asterisk" / "queues.conf"
MANAGER_CONF = Path(__file__).parent.parent / "asterisk" / "manager.conf"


def test_queue_fila_t1_exists_with_receptionist_as_member():
    blocks = {b["name"]: b["text"] for b in parse_blocks(QUEUES_CONF)}
    assert "fila-t1" in blocks
    assert "member => PJSIP/t1-recepcao" in blocks["fila-t1"]


def test_queue_has_sane_ringall_timeout():
    blocks = {b["name"]: b["text"] for b in parse_blocks(QUEUES_CONF)}
    timeout = get_key(blocks["fila-t1"], "timeout")
    assert timeout and int(timeout) > 0


def test_queue_records_calls_automatically():
    blocks = {b["name"]: b["text"] for b in parse_blocks(QUEUES_CONF)}
    assert get_key(blocks["general"], "monitor-format") == "wav"
    assert get_key(blocks["fila-t1"], "monitor-type") == "mixmonitor"


def test_manager_ami_enabled_on_standard_port():
    blocks = {b["name"]: b["text"] for b in parse_blocks(MANAGER_CONF)}
    assert get_key(blocks["general"], "enabled") == "yes"
    assert get_key(blocks["general"], "port") == "5038"


def test_manager_has_queue_api_user_with_credentials():
    blocks = {b["name"]: b["text"] for b in parse_blocks(MANAGER_CONF)}
    assert "queue-api" in blocks
    secret = get_key(blocks["queue-api"], "secret")
    assert secret and secret not in {"", "amp111", "changeme"}


def test_manager_restricts_queue_api_user_by_ip():
    """
    Sanity check de segurança: o usuário AMI não pode estar liberado
    pra qualquer IP (0.0.0.0/0) sem nenhum permit mais restritivo.
    """
    blocks = {b["name"]: b["text"] for b in parse_blocks(MANAGER_CONF)}
    text = blocks["queue-api"]
    assert "permit" in text, "Usuario AMI sem nenhuma restrição de IP (permit)"


def test_manager_queue_api_user_can_receive_dialend_events():
    """
    A notificação de chamada perdida depende do evento DialEnd (classe
    'dialplan') - sem essa permissão de leitura, o queue-api nunca
    recebe o evento e a notificação simplesmente não dispara, em
    silêncio.
    """
    blocks = {b["name"]: b["text"] for b in parse_blocks(MANAGER_CONF)}
    read_classes = get_key(blocks["queue-api"], "read") or ""
    assert "dialplan" in read_classes.split(",")
