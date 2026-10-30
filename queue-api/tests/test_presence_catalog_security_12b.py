import pytest
from presence import validate_presence_input, load_presence, set_presence

def test_multiline_presence_note_is_rejected():
    assert not validate_presence_input({"status":"reuniao","note":"Em reunião\nAdmin"})[0]
    assert validate_presence_input({"status":"reuniao","note":"Em reunião"})[0]

def test_symlink_presence_file_does_not_expose_other_content(tmp_path):
    private = tmp_path / "private.json"
    private.write_text('{"t1-1001":{"status":"ferias","note":"private"}}')
    link = tmp_path / "presence.json"
    link.symlink_to(private)
    with pytest.raises(ValueError):
        load_presence(link)
    with pytest.raises(ValueError):
        set_presence(link, "t1-1001", "ausente")
    assert "private" in private.read_text()
