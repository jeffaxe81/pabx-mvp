"""AstDB não é considerado atualizado sem confirmação de sucesso AMI."""
import pytest

from ami_client import AMIClient
import server


WRITES = [
    ("register_extension_mapping", ("1100", "operator", "t3"),
     {"Action": "DBPut", "Family": "extension-map-t3", "Key": "1100", "Val": "operator"}),
    ("unregister_extension_mapping", ("1100", "t3"),
     {"Action": "DBDel", "Family": "extension-map-t3", "Key": "1100"}),
    ("register_tenant_did", ("5511988881111", "t3"),
     {"Action": "DBPut", "Family": "tenant-did", "Key": "5511988881111", "Val": "t3"}),
    ("unregister_tenant_did", ("5511988881111",),
     {"Action": "DBDel", "Family": "tenant-did", "Key": "5511988881111"}),
]


@pytest.mark.parametrize("method,args,expected", WRITES)
def test_astdb_mutations_require_ack_success(monkeypatch, method, args, expected):
    client = AMIClient("127.0.0.1", 5038, "admin-api", "test-only")
    sent = []
    monkeypatch.setattr(client, "_send_action",
                        lambda fields: sent.append(fields) or {"Response": "Success"})
    assert getattr(client, method)(*args) == {"Response": "Success"}
    assert sent == [expected]


@pytest.mark.parametrize("method,args,expected", WRITES)
@pytest.mark.parametrize("failure_reply", [
    {"Response": "Error", "Message": "internal-private-server-data"},
    {"Response": "Follows"},
    {},
])
def test_astdb_error_replies_fail_closed_without_leaking_message(
    monkeypatch, method, args, expected, failure_reply
):
    client = AMIClient("127.0.0.1", 5038, "admin-api", "test-only")
    monkeypatch.setattr(client, "_send_action", lambda fields: failure_reply)
    with pytest.raises(ConnectionError, match="AstDB") as captured:
        getattr(client, method)(*args)
    assert "internal-private-server-data" not in str(captured.value)


def test_astdb_mapping_failure_restores_published_configs(tmp_path, monkeypatch):
    generated = tmp_path / "generated"
    generated.mkdir()
    initial = generated / "pjsip_dynamic.conf"
    initial.write_text("old", encoding="utf-8")
    monkeypatch.setattr(server, "ASTERISK_CONF_DIR", str(tmp_path))
    monkeypatch.setattr(server, "load_store", lambda path: [])
    monkeypatch.setattr(server, "known_extension_tenants", lambda: {"t1", "t3"})
    monkeypatch.setattr(server, "render_all", lambda *args, **kwargs:
                        {"pjsip_dynamic.conf": "new"})
    seen = []

    class RefusingClient:
        def __init__(self, *args):
            pass
        def connect_and_login(self):
            seen.append("login")
        def register_extension_mapping(self, *args):
            seen.append("reject")
            assert initial.read_text(encoding="utf-8") == "new"
            raise ConnectionError("Asterisk recusou alteração AstDB")
        def reload_pjsip_and_dialplan(self):
            seen.append("rollback_reload")
            assert initial.read_text(encoding="utf-8") == "old"
            return {"pjsip": "Follows"}
        def close(self):
            seen.append("close")

    monkeypatch.setattr(server, "AMIClient", RefusingClient)
    with pytest.raises(ConnectionError, match="AstDB"):
        server.regenerate_and_reload(
            [("register_extension_mapping", ("1100", "operator", "t3"))]
        )
    assert seen == ["login", "reject", "rollback_reload", "close"]
    assert initial.read_text(encoding="utf-8") == "old"
