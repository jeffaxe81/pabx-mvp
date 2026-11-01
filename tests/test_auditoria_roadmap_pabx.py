"""Teste da auditoria: resultados sao apenas indicios, nunca homologacao."""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/auditar_roadmap_pabx.py"


def test_auditoria_cobre_100_candidatos_sem_aprovar_automaticamente():
    spec = importlib.util.spec_from_file_location("auditoria_pabx", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.scan()
    assert len(result) == 100
    assert len({entry["id"] for entry in result}) == 100
    assert all(entry["status"] == "REVISAR_MANUALMENTE" for entry in result)
    assert all(isinstance(entry["indicios"], list) for entry in result)
