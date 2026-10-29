"""Criação de tenant recuperável, com arquivos e AMI simulados."""
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

import tenant_provisioning as provision
from tenants import load_tenants

TENANT = {"tenant_id": "t3", "did": "5511900003333", "display_name": "Empresa Teste"}
SUCCESS = {name: "Follows" for name in provision.RELOAD_COMPONENTS}


def environment(tmp_path):
    root = tmp_path / "asterisk"
    for directory in (
        "pjsip_tenants", "queues_tenants", "extensions_tenants",
        "voicemail_tenants", "parking_tenants", "generated",
    ):
        (root / directory).mkdir(parents=True)
    return root, tmp_path / "tenants.json"


def credentials():
    return {
        "t3-recepcao": "A" * 32,
        "t3-recepcao-2": "B" * 32,
    }, {"t3-1001": "24681357", "t3-recepcao": "12345678", "t3-recepcao-2": "87654321"}


def make_factory(events, failure=None, compensation_fails=False):
    class Client:
        def __init__(self):
            self.compensation = len([e for e in events if e == "connect"]) > 0
        def connect_and_login(self):
            events.append("connect")
            if self.compensation and compensation_fails:
                raise ConnectionError("AMI fora do ar")
            if failure == "login":
                raise ConnectionError("AMI indisponível")
        def register_tenant_did(self, did, tid):
            events.append("register")
            if failure == "register":
                raise ConnectionError("DBPut pode ter sido aplicado")
        def unregister_tenant_did(self, did):
            events.append("unregister")
        def reload_pjsip_and_dialplan(self):
            events.append("rollback_reload" if self.compensation else "reload")
            if failure == "reload" and not self.compensation:
                raise RuntimeError("Falha de reload")
            return SUCCESS
        def close(self):
            events.append("close")
    return Client


def run(root, registry, factory):
    sip, pins = credentials()
    return provision.provision_tenant(
        root, registry, [], TENANT, sip, pins, factory
    )


def generated_files(root):
    return list(root.rglob("t3.conf")) + list((root / "generated").glob("*-t3.conf")) + list((root / "generated").glob("*_t3.conf"))


def test_creation_commits_8_files_did_and_registry_only_after_reload(tmp_path):
    root, registry = environment(tmp_path)
    events = []
    result = run(root, registry, make_factory(events))
    assert result == SUCCESS
    assert events == ["connect", "register", "reload", "close"]
    assert load_tenants(registry) == [TENANT]
    files = provision.build_tenant_files(root, "t3", *credentials())
    assert len(files) == 8
    assert all(target.is_file() and target.read_text(encoding="utf-8") == content
               for target, content in files.items())
    assert not list(root.rglob(".tenant-stage-*"))


@pytest.mark.parametrize("failure", ["login", "register", "reload"])
def test_failures_leave_no_files_or_registry_and_compensate_did(tmp_path, failure):
    root, registry = environment(tmp_path)
    events = []
    with pytest.raises(provision.TenantProvisionError) as caught:
        run(root, registry, make_factory(events, failure))
    assert not caught.value.rollback_incomplete
    assert not registry.exists()
    assert not generated_files(root)
    assert not list(root.rglob(".tenant-stage-*"))
    if failure != "login":
        assert "unregister" in events
        assert "rollback_reload" in events
    else:
        assert "unregister" not in events


def test_failed_compensation_is_visible_for_manual_reconciliation(tmp_path):
    root, registry = environment(tmp_path)
    events = []
    with pytest.raises(provision.TenantProvisionError) as caught:
        run(root, registry, make_factory(events, "register", compensation_fails=True))
    assert caught.value.rollback_incomplete
    assert not generated_files(root)
    assert not registry.exists()


def test_registry_write_failure_compensates_did_without_exposing_credentials(tmp_path, monkeypatch):
    root, registry = environment(tmp_path)
    events = []
    def fail_write(*args):
        raise OSError("falha de disco")
    monkeypatch.setattr(provision, "save_tenants", fail_write)
    with pytest.raises(provision.TenantProvisionError):
        run(root, registry, make_factory(events))
    assert events.count("unregister") == 1
    assert not generated_files(root)
    assert not registry.exists()


def test_existing_file_is_never_overwritten_even_with_missing_registry(tmp_path):
    root, registry = environment(tmp_path)
    conflict = root / "pjsip_tenants" / "t3.conf"
    conflict.write_text("configuração preexistente", encoding="utf-8")
    events = []
    with pytest.raises(provision.TenantProvisionError):
        run(root, registry, make_factory(events))
    assert conflict.read_text(encoding="utf-8") == "configuração preexistente"
    assert "connect" not in events
    assert not registry.exists()
    assert not list(root.rglob(".tenant-stage-*"))


def test_missing_or_symlinked_directory_refuses_publication(tmp_path):
    root, registry = environment(tmp_path)
    missing = root / "queues_tenants"
    missing.rmdir()
    events = []
    with pytest.raises(provision.TenantProvisionError):
        run(root, registry, make_factory(events))
    assert not generated_files(root)
    assert not list(root.rglob(".tenant-stage-*"))
    assert events == []


def test_registry_preexisting_records_are_preserved(tmp_path):
    root, registry = environment(tmp_path)
    sip, pins = credentials()
    prior = [{"tenant_id": "t5", "did": "5511900005555", "display_name": "Empresa Antiga"}]
    assert provision.provision_tenant(root, registry, prior, TENANT, sip, pins, make_factory([])) == SUCCESS
    assert load_tenants(registry) == prior + [TENANT]


def test_lock_serializes_admin_operations_with_same_tenant():
    lock = provision.TENANT_TRANSACTION_LOCK
    calls = []
    def task(value):
        with lock:
            calls.append(("start", value))
            calls.append(("end", value))
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(task, range(40)))
    assert all(calls[i][0] == "start" and calls[i+1][0] == "end"
               for i in range(0, len(calls), 2))
