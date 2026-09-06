"""
Testes do webphone/manifest.json - garante que os campos obrigatórios
pra instalação como PWA existem, e que os ícones referenciados
existem de verdade no disco.
"""
import json
from pathlib import Path

WEBPHONE_DIR = Path(__file__).parent.parent / "webphone"
MANIFEST_PATH = WEBPHONE_DIR / "manifest.json"


def load_manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_is_valid_json():
    manifest = load_manifest()
    assert isinstance(manifest, dict)


def test_manifest_has_required_installability_fields():
    manifest = load_manifest()
    for field in ("name", "short_name", "start_url", "display", "icons"):
        assert field in manifest, f"Campo obrigatório ausente no manifest: {field}"

    assert manifest["display"] == "standalone"


def test_manifest_has_at_least_one_large_icon():
    manifest = load_manifest()
    sizes = {icon["sizes"] for icon in manifest["icons"]}
    assert "512x512" in sizes, "Instalação como PWA exige um ícone de 512x512"


def test_manifest_includes_a_maskable_icon():
    """
    Ícone maskable é o que faz o ícone não ficar cortado feio em
    launchers Android que aplicam máscaras de forma (círculo, etc.).
    """
    manifest = load_manifest()
    purposes = {icon.get("purpose") for icon in manifest["icons"]}
    assert "maskable" in purposes


def test_all_referenced_icon_files_exist_on_disk():
    manifest = load_manifest()
    for icon in manifest["icons"]:
        icon_path = WEBPHONE_DIR / icon["src"]
        assert icon_path.is_file(), f"Ícone referenciado no manifest não existe: {icon['src']}"
