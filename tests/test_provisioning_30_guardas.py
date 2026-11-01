"""PV-01..PV-30: cada regra tem um cenário negativo executável."""
import importlib.util
import json
from pathlib import Path
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "provisioning" / "generate.py"


def module():
    spec = importlib.util.spec_from_file_location("axe_pv_30", SCRIPT)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def device(mac="aabbccddeeff"):
    return {"mac": mac, "vendor": "yealink", "ramal": "t1-1001",
            "nome": "Recepcao", "senha": "SenhaForte123!", "servidor": "pabx.local"}


def fixture_tree(tmp_path, monkeypatch):
    mod = module()
    source = tmp_path / "devices.json"
    templates = tmp_path / "templates"
    templates.mkdir()
    template = templates / "yealink.cfg.tpl"
    template.write_text(
        "user={{RAMAL}}\nname={{NOME}}\npass={{SENHA}}\nserver={{SERVIDOR}}\n",
        encoding="utf-8")
    output = tmp_path / "files"
    monkeypatch.setattr(mod, "DEVICES_FILE", str(source))
    monkeypatch.setattr(mod, "TEMPLATES_DIR", str(templates))
    monkeypatch.setattr(mod, "OUTPUT_DIR", str(output))
    return mod, source, template, output


@pytest.mark.parametrize("case,code", [(i, f"PV-{i:02d}") for i in range(1, 31)])
def test_30_bloqueios_independentes_sem_publicacao_parcial(tmp_path, monkeypatch, case, code):
    mod, source, template, output = fixture_tree(tmp_path, monkeypatch)
    records = [device()]
    data = {"devices": records}
    if case == 1:
        source.symlink_to(tmp_path / "inexistente")
    elif case == 2:
        source.write_bytes(b" " * (mod.MAX_MANIFEST_BYTES + 1))
    elif case == 3:
        source.write_text("{json invalido")
    elif case == 4:
        data = []
    elif case == 5:
        data = {}
    elif case == 6:
        data = {"devices": {}}
    elif case == 7:
        data = {"devices": [device(f"{i:012x}") for i in range(mod.MAX_DEVICES + 1)]}
    elif case == 8:
        records[0] = "nao-objeto"
    elif case == 9:
        records[0].pop("mac")
    elif case == 10:
        records[0]["mac"] = 123
    elif case == 11:
        records[0]["mac"] = "../../escape"
    elif case == 12:
        records.append(device("AABBCCDDEEFF"))
    elif case == 13:
        records[0].pop("vendor")
    elif case == 14:
        records[0]["vendor"] = 3
    elif case == 15:
        records[0]["vendor"] = " "
    elif case == 16:
        records[0].pop("ramal")
    elif case == 17:
        records[0].pop("nome")
    elif case == 18:
        records[0].pop("senha")
    elif case == 19:
        records[0].pop("servidor")
    elif case == 20:
        records[0]["senha"] = 7
    elif case == 21:
        records[0]["senha"] = " "
    elif case == 22:
        records[0]["nome"] = "Recepcao\nconfig=inject"
    elif case == 23:
        records[0]["senha"] = "{{SENHA}}"
    elif case == 24:
        records[0]["nome"] = "x" * (mod.LIMITS["nome"] + 1)
    elif case == 25:
        template.unlink()
        template.symlink_to(tmp_path / "inexistente")
    elif case == 26:
        template.write_bytes(b"x" * (mod.MAX_TEMPLATE_BYTES + 1))
    elif case == 27:
        template.write_bytes(b"\xff")
    elif case == 28:
        template.write_text("user={{RAMAL}}\nname={{NOME}}\npass={{SENHA}}")
    elif case == 29:
        template.write_text(template.read_text() + "\nunknown={{EXTRA}}")
    elif case == 30:
        external = tmp_path / "external"
        external.mkdir()
        output.symlink_to(external, target_is_directory=True)
    if not source.exists() and not source.is_symlink():
        source.write_text(json.dumps(data))
    elif case not in (1, 2, 3):
        source.write_text(json.dumps(data))
    with pytest.raises(ValueError, match=code):
        mod.main()
    if case == 30:
        assert list((tmp_path / "external").iterdir()) == []
    elif output.is_dir():
        assert list(output.iterdir()) == []


def test_geracao_de_dois_tenants_preserva_credenciais_separadas(tmp_path, monkeypatch):
    mod, source, _template, output = fixture_tree(tmp_path, monkeypatch)
    source.write_text(json.dumps({"devices": [
        device(), {**device("001122334455"), "ramal": "t2-1001",
                   "senha": "SegredoT2", "servidor": "t2.local"}
    ]}))
    mod.main()
    a = (output / "aabbccddeeff.cfg").read_text()
    b = (output / "001122334455.cfg").read_text()
    assert "SenhaForte123!" in a and "SenhaForte123!" not in b
    assert "SegredoT2" in b and "SegredoT2" not in a
    assert "{{" not in a + b


def test_fornecedor_desconhecido_mantem_compatibilidade(tmp_path, monkeypatch, capsys):
    mod, source, _template, output = fixture_tree(tmp_path, monkeypatch)
    source.write_text(json.dumps({"devices": [{**device(), "vendor": "desconhecido"}]}))
    mod.main()
    assert "AVISO" in capsys.readouterr().out
    assert not list(output.glob("*.cfg"))


def test_falha_de_replace_preserva_versao_anterior(tmp_path, monkeypatch):
    mod, source, _template, output = fixture_tree(tmp_path, monkeypatch)
    source.write_text(json.dumps({"devices": [device()]}))
    output.mkdir()
    old = output / "aabbccddeeff.cfg"
    old.write_text("antigo")
    def fail(*_args):
        raise OSError("falha simulada")
    monkeypatch.setattr(mod.os, "replace", fail)
    with pytest.raises(OSError):
        mod.main()
    assert old.read_text() == "antigo"
    assert not list(output.glob("*.tmp"))


def test_link_simbolico_de_arquivo_nao_sobrescreve_segredo_externo(tmp_path, monkeypatch):
    mod, source, _template, output = fixture_tree(tmp_path, monkeypatch)
    source.write_text(json.dumps({"devices": [device()]}))
    output.mkdir()
    external = tmp_path / "externo"
    external.write_text("inalterado")
    (output / "aabbccddeeff.cfg").symlink_to(external)
    with pytest.raises(ValueError, match="PV-30"):
        mod.main()
    assert external.read_text() == "inalterado"
