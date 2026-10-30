import importlib.util
import json
from pathlib import Path
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "provisioning" / "generate.py"

def test_mac_traversal_and_duplicates_fail_before_publication(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("provision_test", SCRIPT)
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    for macs in (["../../escape"], ["aabbccddeeff", "AABBCCDDEEFF"]):
        catalog = tmp_path / "devices.json"
        catalog.write_text(json.dumps({"devices": [{"mac": mac, "vendor": "yealink", "ramal": "t1-1", "nome": "test", "senha": "secret", "servidor": "pabx"} for mac in macs]}))
        output = tmp_path / "files"
        monkeypatch.setattr(generator, "DEVICES_FILE", str(catalog))
        monkeypatch.setattr(generator, "OUTPUT_DIR", str(output))
        with pytest.raises(ValueError):
            generator.main()
        assert not list(output.glob("*.cfg"))
