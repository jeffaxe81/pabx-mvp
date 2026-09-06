"""
Testes do provisioning/generate.py: garante que, a partir de um
devices.json de teste, os arquivos gerados batem com o esperado e não
sobra nenhum placeholder ({{...}}) sem substituir.
"""
import importlib.util
import json
import re
import tempfile
from pathlib import Path

PROVISIONING_DIR = Path(__file__).parent.parent / "provisioning"


def load_generate_module():
    spec = importlib.util.spec_from_file_location("generate", PROVISIONING_DIR / "generate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_devices_json_is_valid():
    data = json.loads((PROVISIONING_DIR / "devices.json").read_text(encoding="utf-8"))
    assert "devices" in data
    for device in data["devices"]:
        for field in ("mac", "vendor", "ramal", "nome", "senha", "servidor"):
            assert field in device, f"Dispositivo sem campo obrigatório '{field}': {device}"


def test_generated_files_have_no_leftover_placeholders(tmp_path, monkeypatch):
    """
    Roda o gerador de verdade contra um devices.json isolado em pasta
    temporária, e confere que nenhum {{PLACEHOLDER}} sobrou no arquivo
    final - isso indicaria um campo não mapeado no generate.py.
    """
    module = load_generate_module()

    fake_devices = {
        "devices": [
            {
                "mac": "aabbccddeeff",
                "vendor": "yealink",
                "ramal": "t1-9999",
                "nome": "Ramal de Teste",
                "senha": "senha-de-teste",
                "servidor": "pabx.teste.local",
            }
        ]
    }
    devices_file = tmp_path / "devices.json"
    devices_file.write_text(json.dumps(fake_devices), encoding="utf-8")

    output_dir = tmp_path / "files"

    monkeypatch.setattr(module, "DEVICES_FILE", str(devices_file))
    monkeypatch.setattr(module, "OUTPUT_DIR", str(output_dir))

    module.main()

    generated = output_dir / "aabbccddeeff.cfg"
    assert generated.exists(), "Arquivo de provisionamento não foi gerado"

    content = generated.read_text(encoding="utf-8")
    assert "{{" not in content, "Sobrou placeholder não substituído no arquivo gerado"
    assert "t1-9999" in content
    assert "senha-de-teste" in content
    assert "pabx.teste.local" in content


def test_unknown_vendor_is_skipped_without_crashing(tmp_path, monkeypatch, capsys):
    module = load_generate_module()

    fake_devices = {
        "devices": [
            {
                "mac": "000000000000",
                "vendor": "fabricante-inexistente",
                "ramal": "t1-0000",
                "nome": "Teste",
                "senha": "x",
                "servidor": "x",
            }
        ]
    }
    devices_file = tmp_path / "devices.json"
    devices_file.write_text(json.dumps(fake_devices), encoding="utf-8")
    output_dir = tmp_path / "files"

    monkeypatch.setattr(module, "DEVICES_FILE", str(devices_file))
    monkeypatch.setattr(module, "OUTPUT_DIR", str(output_dir))

    module.main()  # não deve lançar exceção

    captured = capsys.readouterr()
    assert "AVISO" in captured.out
