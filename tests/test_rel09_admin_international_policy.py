"""REL-09: controle administrativo da política de discagem."""
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "admin-api"))
from ami_client import AMIClient


def test_alteracao_da_politica_requer_papel_admin():
    source = (ROOT / "admin-api/server.py").read_text(encoding="utf-8")
    handler = source.split("    def _handle_set_international_policy(self):", 1)[1].split("\n    def ", 1)[0]
    assert handler.index('_require_role({"admin"})') < handler.index("_read_json_body()")
    assert handler.index('_require_role({"admin"})') < handler.index("set_international_block")
    assert 'type(blocked) is not bool' in handler
    assert "validate_tenant" in handler


def test_escrita_astdb_e_restrita_a_chave_internacional():
    client = AMIClient("127.0.0.1", 5038, "test", "test")
    calls = []
    client._send_required_db_action = lambda fields: calls.append(fields) or {"Response": "Success"}
    client.set_international_block("t1", True)
    client.set_international_block("t2", False)
    assert calls == [
        {"Family": "politica-externa-t1", "Key": "internacional", "Action": "DBPut", "Val": "bloquear"},
        {"Family": "politica-externa-t2", "Key": "internacional", "Action": "DBDel"},
    ]


def test_rejeita_tenant_invalido_sem_acessar_astdb():
    client = AMIClient("127.0.0.1", 5038, "test", "test")
    client._send_required_db_action = lambda fields: (_ for _ in ()).throw(AssertionError("não deveria escrever"))
    for tenant in ("", "t1/../t2", "admin", "t1;cmd"):
        try:
            client.set_international_block(tenant, True)
        except ValueError:
            continue
        raise AssertionError("tenant inválido aceito")
