"""Regressão executável de isolamento no wizard; não simula chamada SIP."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("axe_tenants", ROOT / "admin-api" / "tenants.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_tenants_dinamicos_isolam_contexto_blocklist_e_identidade():
    for tenant, other in (("t3", "t4"), ("t4", "t3"), ("t15", "t16")):
        dial = module.render_tenant_extensions(tenant)
        assert f"[{tenant}-internal]" in dial
        assert f"Set(TENANT={tenant})" in dial
        assert f"DB(blocklist-{tenant}/" in dial
        assert f"DB(blocklist-{other}/" not in dial
        outbound = dial.split("exten => _0.,1,Set(DESTINO=", 1)[1].split("exten => numero-bloqueado,1", 1)[0]
        assert outbound.index(f"Set(TENANT={tenant})") < outbound.index("Gosub(politica-externa,s,1)") < outbound.index("Dial(PJSIP/")
        assert "GOSUB_RETVAL" in outbound


def test_wizard_nega_duplicidade_de_did_e_tenant():
    existing = [{"tenant_id": "t3", "did": "11999990000", "display_name": "Empresa A"}]
    data = {"tenant_id": "t4", "did": "11999990000", "display_name": "Empresa B"}
    ok, error, _ = module.validate_tenant_creation_input(data, existing)
    assert not ok and "DID" in error
    data["did"] = "11999990001"
    data["tenant_id"] = "t3"
    ok, error, _ = module.validate_tenant_creation_input(data, existing)
    assert not ok and "tenant" in error


def test_wizard_gera_senhas_distintas_e_contextos_corretos():
    for tenant in ("t3", "t4"):
        credentials = module.generate_tenant_credentials(tenant)
        assert len(set(credentials.values())) == 2
        rendered = module.render_tenant_pjsip(tenant, credentials)
        assert f"context={tenant}-internal" in rendered
        assert f"context={'t4' if tenant == 't3' else 't3'}-internal" not in rendered
        for password in credentials.values():
            assert len(password) >= 32
            assert password in rendered
