"""REL-15: regressão funcional local de provisionamento entre tenants.

Gera arquivos em diretório temporário, sem publicar configurações reais.
"""
import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "provisioning" / "generate.py"


def test_provisionamento_gera_arquivos_isolados_por_mac_e_tenant(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("provision_rel15", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    devices = [
        {"mac": "aabbccddeeff", "vendor": "yealink", "ramal": "t1-1001",
         "nome": "Ramal T1", "senha": "credencial-tenant-1", "servidor": "t1.local"},
        {"mac": "001122334455", "vendor": "yealink", "ramal": "t2-1001",
         "nome": "Ramal T2", "senha": "credencial-tenant-2", "servidor": "t2.local"},
    ]
    catalog = tmp_path / "devices.json"
    catalog.write_text(json.dumps({"devices": devices}), encoding="utf-8")
    output = tmp_path / "files"
    monkeypatch.setattr(module, "DEVICES_FILE", str(catalog))
    monkeypatch.setattr(module, "OUTPUT_DIR", str(output))

    module.main()

    assert {p.name for p in output.glob("*.cfg")} == {
        "aabbccddeeff.cfg", "001122334455.cfg"
    }
    t1 = (output / "aabbccddeeff.cfg").read_text(encoding="utf-8")
    t2 = (output / "001122334455.cfg").read_text(encoding="utf-8")
    for value in ("t1-1001", "credencial-tenant-1", "t1.local"):
        assert value in t1
        assert value not in t2
    for value in ("t2-1001", "credencial-tenant-2", "t2.local"):
        assert value in t2
        assert value not in t1
    assert "{{" not in t1 and "{{" not in t2
