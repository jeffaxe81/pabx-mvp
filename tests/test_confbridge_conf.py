"""
Testes estáticos do asterisk/confbridge.conf (backlog #43 - sala de
conferência ad-hoc). Não sobe o Asterisk de verdade.
"""
from pathlib import Path

from conf_parser import parse_blocks, get_key

CONFBRIDGE_CONF = Path(__file__).parent.parent / "asterisk" / "confbridge.conf"


def load_blocks():
    return parse_blocks(CONFBRIDGE_CONF)


def blocks_as_dict(blocks):
    return {b["name"]: b["text"] for b in blocks}


def test_default_profiles_exist():
    blocks = blocks_as_dict(load_blocks())
    assert "default_bridge" in blocks
    assert "default_user" in blocks
    assert "default_menu" in blocks


def test_bridge_profile_has_reasonable_member_limit():
    blocks = blocks_as_dict(load_blocks())
    assert get_key(blocks["default_bridge"], "max_members") is not None


def test_conference_recording_disabled_by_default():
    """
    Gravar conferência não foi implementado como funcionalidade
    própria ainda (auditoria item #12 mais amplo) - por enquanto,
    desligado por padrão em vez de gravar parcialmente/sem aviso.
    """
    blocks = blocks_as_dict(load_blocks())
    assert get_key(blocks["default_bridge"], "record_conference") == "no"


def test_participants_are_announced_on_join_and_leave():
    """Sem isso, ninguém saberia quem entrou/saiu da sala - básico de usabilidade de conferência."""
    blocks = blocks_as_dict(load_blocks())
    assert get_key(blocks["default_user"], "announce_join_leave") == "yes"


def test_mute_toggle_bound_to_star_key():
    blocks = blocks_as_dict(load_blocks())
    assert get_key(blocks["default_menu"], "*") == "toggle_mute"
