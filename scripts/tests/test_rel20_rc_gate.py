"""REL-20: garantias de que o RC local nao converte pendencias em GO."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "rel20_rc_gate.py"
spec = importlib.util.spec_from_file_location("rel20_rc_gate_under_test", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

FILES = (
    "VERSION",
    "docs/releases/axe-pabx-0.1.0-rc.1.json",
    "docs/release-fechamento-20-entregas.md",
    "docs/quality/provas-operacionais-diferidas.json",
    "docs/modelo-homologacao-pabx.json",
)


def sandbox(tmp_path):
    for rel in FILES:
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dest)
    return tmp_path


def change_json(root, rel, change):
    path = root / rel
    value = json.loads(path.read_text(encoding="utf-8"))
    change(value)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_rc_tem_20_marcos_sem_prova_de_producao():
    report = mod.verify(ROOT)
    assert report["engineering_release_percent"] == 100
    assert report["release_checklist_completed"] == 20
    assert report["deferred_operational_checks"] == 15
    assert report["unperformed_manual_homologation_scenarios"] == 13
    assert report["operational_go_authorized"] is False
    assert report["ci_approval_verified_by_this_tool"] is False
    assert report["git_tag_created_by_this_tool"] is False


@pytest.mark.parametrize("field,value", [
    ("production_deployment_executed", True),
    ("operational_go_authorized", True),
    ("real_telecom_operator_tested", True),
    ("physical_ip_phone_tested", True),
    ("contact_center_in_scope", True),
    ("ai_in_scope", True),
    ("git_tag_created_by_this_change", True),
    ("milestones_completed", 19),
    ("release_acceptance", "PRODUCTION_GO"),
])
def test_rc_rejeita_falsa_prontidao_operacional(tmp_path, field, value):
    root = sandbox(tmp_path)
    change_json(root, mod.MANIFEST, lambda j: j.__setitem__(field, value))
    with pytest.raises(ValueError, match="REL20-MANIFEST-CONFLICT"):
        mod.verify(root)


def test_rc_rejeita_milestone_pendente_e_progressao_incorreta(tmp_path):
    root = sandbox(tmp_path)
    path = root / mod.RELEASE
    value = path.read_text(encoding="utf-8").replace(
        "- [x] **REL-20", "- [ ] **REL-20")
    path.write_text(value, encoding="utf-8")
    with pytest.raises(ValueError, match="REL20-MILESTONES-INCOMPLETE"):
        mod.verify(root)


def test_rc_rejeita_alteracao_falsa_do_go_no_inventario(tmp_path):
    root = sandbox(tmp_path)
    change_json(root, mod.OPERATIONS,
                lambda j: j.__setitem__("operational_go_authorized", True))
    with pytest.raises(ValueError, match="REL20-OPS-GATE-INVALID"):
        mod.verify(root)


def test_rc_rejeita_prova_operacional_inventada(tmp_path):
    root = sandbox(tmp_path)
    def inject(j):
        j["pending_checks"][0]["status"] = "VERIFIED"
        j["pending_checks"][0]["evidence"] = "url-ficticia"
    change_json(root, mod.OPERATIONS, inject)
    with pytest.raises(ValueError, match="REL20-OPS-GATE-INVALID"):
        mod.verify(root)


def test_rc_rejeita_homologacao_sem_aceite(tmp_path):
    root = sandbox(tmp_path)
    change_json(root, mod.HOMOLOGATION, lambda j: j["checks"]["sip_registration"].update(
        status="passed", evidence="inventada"))
    with pytest.raises(ValueError, match="REL20-HOMOLOGATION-INVALID"):
        mod.verify(root)


def test_rc_rejeita_versao_alterada(tmp_path):
    root = sandbox(tmp_path)
    (root / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="REL20-VERSION-INVALID"):
        mod.verify(root)


def test_rc_rejeita_link_simbolico_de_manifesto(tmp_path):
    root = sandbox(tmp_path)
    target = root / mod.MANIFEST
    real = tmp_path / "real.json"
    target.replace(real)
    target.symlink_to(real)
    with pytest.raises(ValueError, match="REL20-FILE-INVALID"):
        mod.verify(root)


def test_rc_rejeita_chaves_duplicadas_no_manifesto(tmp_path):
    root = sandbox(tmp_path)
    target = root / mod.MANIFEST
    raw = target.read_text(encoding="utf-8")
    target.write_text(raw.replace('"schema_version": 1,',
                                  '"schema_version": 1, "schema_version": 1,'),
                      encoding="utf-8")
    with pytest.raises(ValueError, match="REL20-JSON-DUPLICATE"):
        mod.verify(root)
