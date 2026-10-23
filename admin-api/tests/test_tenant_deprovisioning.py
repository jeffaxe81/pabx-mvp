"""Exclusão de tenant reversível em cenários AMI e disco simulados."""
import pytest

import tenant_deprovisioning as removal
from tenant_provisioning import build_tenant_files
from conf_generator import render_pjsip_dynamic
from tenants import save_tenants, load_tenants
from store import save_store, load_store

TENANT = {"tenant_id": "t3", "did": "5511900003333", "display_name": "Empresa Teste"}
OTHER = {"tenant_id": "t4", "did": "5511900004444", "display_name": "Outra Empresa"}
RAMALS = [
    {"name": "oper-t3", "number": 1100, "display_name": "Atendimento t3",
     "tenant": "t3", "password": "A" * 32, "voicemail_pin": "87654321"},
    {"name": "oper-t4", "number": 1100, "display_name": "Atendimento t4",
     "tenant": "t4", "password": "B" * 32, "voicemail_pin": "12345678"},
]
OK = dict.fromkeys(removal.RELOAD_COMPONENTS, "Follows")


def lab(tmp_path):
    root = tmp_path / "asterisk"
    for sub in (
        "pjsip_tenants", "queues_tenants", "extensions_tenants",
        "voicemail_tenants", "parking_tenants", "generated",
    ):
        (root / sub).mkdir(parents=True)
    sip = {"t3-recepcao": "C" * 32, "t3-recepcao-2": "D" * 32}
    pins = {"t3-recepcao": "12345678", "t3-recepcao-2": "87654321"}
    for file, content in build_tenant_files(root, "t3", sip, pins).items():
        file.write_text(content, encoding="utf-8")
    shared = root / "generated" / "pjsip_dynamic.conf"
    shared.write_text(render_pjsip_dynamic(RAMALS), encoding="utf-8")
    registry = tmp_path / "tenants.json"
    store = tmp_path / "extensions.json"
    save_tenants(registry, [TENANT, OTHER])
    save_store(store, RAMALS)
    before = {file: file.read_bytes() for file in removal.tenant_config_paths(root, "t3")}
    before[shared] = shared.read_bytes()
    return root, registry, store, before


def fake_factory(calls, fault=None, fail_recovery=False):
    class Client:
        def __init__(self):
            self.compensating = calls.count("connect") >= 1
        def connect_and_login(self):
            calls.append("connect")
            if fault == "login" and not self.compensating:
                raise ConnectionError("login AMI falhou")
            if fail_recovery and self.compensating:
                raise ConnectionError("AMI de compensação indisponível")
        def unregister_tenant_did(self, did):
            calls.append("unregister")
            if fault == "unregister":
                raise ConnectionError("DBDel pode ter sido aplicado")
        def register_tenant_did(self, did, tenant):
            calls.append("register")
        def reload_pjsip_and_dialplan(self):
            calls.append("compensate_reload" if self.compensating else "reload")
            if fault == "reload" and not self.compensating:
                raise RuntimeError("falha Asterisk")
            return OK
        def close(self):
            calls.append("close")
    return Client


def test_success_removes_only_target_tenant_and_prunes_pjsip(tmp_path):
    root, registry, store, before = lab(tmp_path)
    events = []
    result = removal.remove_tenant(root, registry, store, [TENANT, OTHER], TENANT, fake_factory(events))
    assert result["removed_extensions"] == 1
    assert load_tenants(registry) == [OTHER]
    assert load_store(store) == [RAMALS[1]]
    assert not any(file.exists() for file in before if file.name != "pjsip_dynamic.conf")
    assert "oper-t3" not in (root / "generated" / "pjsip_dynamic.conf").read_text()
    assert "oper-t4" in (root / "generated" / "pjsip_dynamic.conf").read_text()
    assert events == ["connect", "unregister", "reload", "close"]


@pytest.mark.parametrize("fault", ["login", "unregister", "reload"])
def test_ami_failures_restore_every_file_and_original_json(tmp_path, fault):
    root, registry, store, before = lab(tmp_path)
    events = []
    with pytest.raises(removal.TenantRemovalError) as caught:
        removal.remove_tenant(root, registry, store, [TENANT, OTHER], TENANT, fake_factory(events, fault))
    assert not caught.value.rollback_incomplete
    assert load_tenants(registry) == [TENANT, OTHER]
    assert load_store(store) == RAMALS
    assert {file: file.read_bytes() for file in before} == before
    if fault != "login":
        assert "register" in events
        assert "compensate_reload" in events


def test_deletion_rolls_back_and_exposes_incomplete_compensation(tmp_path):
    root, registry, store, before = lab(tmp_path)
    with pytest.raises(removal.TenantRemovalError) as caught:
        removal.remove_tenant(root, registry, store, [TENANT, OTHER], TENANT,
                              fake_factory([], "unregister", fail_recovery=True))
    assert caught.value.rollback_incomplete
    assert load_tenants(registry) == [TENANT, OTHER]
    assert load_store(store) == RAMALS
    assert all(file.read_bytes() == contents for file, contents in before.items())


def test_failed_tenant_registry_save_restores_ramais_and_did(tmp_path, monkeypatch):
    root, registry, store, before = lab(tmp_path)
    events = []
    def fail_save(*args):
        raise OSError("registro de tenants indisponível")
    monkeypatch.setattr(removal, "save_tenants", fail_save)
    with pytest.raises(removal.TenantRemovalError) as caught:
        removal.remove_tenant(root, registry, store, [TENANT, OTHER], TENANT, fake_factory(events))
    assert not caught.value.rollback_incomplete
    assert load_tenants(registry) == [TENANT, OTHER]
    assert load_store(store) == RAMALS
    assert {file: file.read_bytes() for file in before} == before
    assert "register" in events


def test_missing_tenant_configuration_refuses_deletion_before_ami(tmp_path):
    root, registry, store, before = lab(tmp_path)
    path = root / "voicemail_tenants" / "t3.conf"
    path.unlink()
    events = []
    with pytest.raises(removal.TenantRemovalError):
        removal.remove_tenant(root, registry, store, [TENANT, OTHER], TENANT, fake_factory(events))
    assert events == []
    assert load_tenants(registry) == [TENANT, OTHER]
    assert load_store(store) == RAMALS
    assert all(f.read_bytes() == data for f, data in before.items() if f != path)


def test_symlink_in_tenant_files_is_rejected_without_touching_outside(tmp_path):
    root, registry, store, before = lab(tmp_path)
    target = root / "outside.conf"
    target.write_text("private", encoding="utf-8")
    linked = root / "queues_tenants" / "t3.conf"
    linked.unlink()
    linked.symlink_to(target)
    with pytest.raises(removal.TenantRemovalError):
        removal.remove_tenant(root, registry, store, [TENANT, OTHER], TENANT, fake_factory([]))
    assert target.read_text(encoding="utf-8") == "private"
    assert load_store(store) == RAMALS
