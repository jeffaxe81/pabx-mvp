"""REL-04: manter escopo do simulador local e verificação de prefixos."""
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("rel04_routes", ROOT / "lab/outbound_route_checks.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_nove_cenarios_fechados_sem_tronco():
    assert len(MODULE.CASES) == 9
    assert len({case for case, *_ in MODULE.CASES}) == 9
    assert any(case == "t1-int-block" and result == "DENY"
               for case, _, _, result in MODULE.CASES)
    assert any(case == "t1-int-allow" and result.startswith("SECONDARY:")
               for case, _, _, result in MODULE.CASES)
    assert any(case == "t2-int-allow" and result.startswith("PRIMARY:")
               for case, _, _, result in MODULE.CASES)
    assert any(case == "t1-secondary-blocklist" and result == "DENY"
               for case, _, _, result in MODULE.CASES)


def test_substituicao_exclusiva_no_dialplan_temporario():
    source = (ROOT / "lab/outbound_route_checks.py").read_text(encoding="utf-8")
    assert 'prepared["conf"]' in source
    assert 'value.count(primary)' in source
    assert 'value.count(secondary)' in source
    assert 'value.count(blocked)' in source
    assert 'original.write_text(value' in source
    assert "channel originate Local/" in source
    assert "external_operator_trunks_tested" in source
    assert len(MODULE.required_route_checks()) == 12


def test_selector_regex_t1_usa_argumento_sem_virgula():
    dialplan = (ROOT / "asterisk/extensions.conf").read_text(encoding="utf-8")
    assert 'REGEX("^0" ${DESTINO})' in dialplan
    assert 'REGEX("^0" ,${DESTINO})' not in dialplan
    assert dialplan.index('Gosub(politica-externa,s,1)') < dialplan.index('REGEX("^0" ${DESTINO})')
