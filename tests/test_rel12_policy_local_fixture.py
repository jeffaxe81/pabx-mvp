"""REL-12: fixture isolada preserva o dialplan original e não toca nos troncos."""
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("policy_rel12", ROOT / "lab/policy_runtime_checks.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_rel12_usa_somente_canais_local_sem_troncos():
    cases = MODULE.CASES
    assert len(cases) == 10
    assert len({name for name, _, _, _ in cases}) == len(cases)
    assert all(expected in ("ALLOW", "DENY") for _, _, _, expected in cases)
    assert all(tenant in ("t1", "t2", "t3", "invalid") for _, tenant, _, _ in cases)
    source = (ROOT / "lab/policy_runtime_checks.py").read_text(encoding="utf-8")
    assert "Local/s@lab-rel12-" in source
    assert "channel originate" in source
    assert "Gosub(politica-externa,s,1)" in source
    assert "Dial(PJSIP/" not in source
    assert "operator_trunk_tested" in source


def test_rel12_nao_confunde_resultado_astdb_com_producao():
    requirements = MODULE.required_policy_checks()
    assert len(requirements) == 13
    assert {"policy_decision:t1-int-block", "policy_decision:t2-int-allow",
            "policy_decision:t1-int-reenabled", "policy_decision:bad-tenant"} <= requirements
    assert "policy_no_external_sip" in requirements
