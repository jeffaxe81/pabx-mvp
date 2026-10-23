"""O parser de testes precisa seguir a sintaxe real de templates Asterisk."""
import pytest

from conf_parser import parse_blocks, get_key_inherited


def test_template_marker_is_separate_from_inherited_parent(tmp_path):
    path = tmp_path/'valid.conf'
    path.write_text('[base](!)\ntype=endpoint\n[secure](!,base)\nmedia_encryption=sdes\n[phone](secure)\ncontext=t1-internal\n')
    blocks = parse_blocks(path)
    phone = blocks[-1]
    assert get_key_inherited(phone, 'type', blocks) == 'endpoint'
    assert get_key_inherited(phone, 'media_encryption', blocks) == 'sdes'


def test_invalid_embedded_template_marker_is_not_silently_corrected(tmp_path):
    path = tmp_path/'invalid.conf'
    path.write_text('[base](!)\ntype=endpoint\n[secure](base!)\ncontext=t1-internal\n')
    with pytest.raises(ValueError):
        parse_blocks(path)
