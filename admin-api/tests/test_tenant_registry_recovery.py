"""Falha após os.replace: restore do catálogo deve ser confiável."""
import os
import stat

import pytest

import tenant_provisioning as provision
import tenant_deprovisioning as removal
from tenant_registry_recovery import snapshot_registry, restore_registry
from tenants import load_tenants, save_tenants
from test_tenant_provisioning import (
    TENANT, environment, credentials, make_factory, generated_files,
)
from test_tenant_deprovisioning import (
    TENANT as TARGET, OTHER, RAMALS, lab, fake_factory,
)
from store import load_store


def test_restore_nonexistent_registry_keeps_it_absent(tmp_path):
    path = tmp_path / "missing.json"
    snapshot = snapshot_registry(path)
    path.write_text('[{"unexpected":true}]')
    restore_registry(path, snapshot)
    assert not path.exists()


def test_restore_prior_registry_exact_bytes_and_permissions(tmp_path):
    path = tmp_path / "tenants.json"
    path.write_bytes(b'[{"tenant_id": "t4", "did":"5511900004444"}]\n')
    path.chmod(0o640)
    before = path.read_bytes()
    snapshot = snapshot_registry(path)
    save_tenants(path, [])
    restore_registry(path, snapshot)
    assert path.read_bytes() == before
    assert stat.S_IMODE(path.stat().st_mode) == 0o640


def test_symlink_registry_is_rejected(tmp_path):
    private = tmp_path / "private.json"
    private.write_text("secret")
    link = tmp_path / "tenants.json"
    link.symlink_to(private)
    with pytest.raises(ValueError):
        snapshot_registry(link)
    with pytest.raises(ValueError):
        restore_registry(link, None)
    assert private.read_text() == "secret"


def test_creation_late_save_error_removes_new_registry_and_compensates_did(
    tmp_path, monkeypatch
):
    root, registry = environment(tmp_path)
    events = []
    real_save = provision.save_tenants

    def fail_after_replace(path, records):
        real_save(path, records)
        raise OSError("fsync-directory-after-replace-failed")

    monkeypatch.setattr(provision, "save_tenants", fail_after_replace)
    with pytest.raises(provision.TenantProvisionError) as caught:
        provision.provision_tenant(root, registry, [], TENANT,
                                   *credentials(), make_factory(events))
    assert not caught.value.rollback_incomplete
    assert not registry.exists()
    assert not generated_files(root)
    assert "unregister" in events


def test_creation_late_save_error_preserves_existing_registry_bytes(
    tmp_path, monkeypatch
):
    root, registry = environment(tmp_path)
    old = [{"tenant_id":"t5","did":"5511900005555","display_name":"Anterior"}]
    save_tenants(registry, old)
    original_bytes = registry.read_bytes()
    real_save = provision.save_tenants

    def fail_late(path, records):
        real_save(path, records)
        raise OSError("crash-after-replace")

    monkeypatch.setattr(provision, "save_tenants", fail_late)
    with pytest.raises(provision.TenantProvisionError):
        provision.provision_tenant(
            root, registry, old, TENANT, *credentials(), make_factory([])
        )
    assert registry.read_bytes() == original_bytes
    assert load_tenants(registry) == old


def test_removal_late_save_error_restores_exact_registry_and_extensions(
    tmp_path, monkeypatch
):
    root, registry, store, before_files = lab(tmp_path)
    original_registry = registry.read_bytes()
    real_save = removal.save_tenants

    def fail_late(path, records):
        real_save(path, records)
        raise OSError("exception-after-publication")

    monkeypatch.setattr(removal, "save_tenants", fail_late)
    events = []
    with pytest.raises(removal.TenantRemovalError) as caught:
        removal.remove_tenant(root, registry, store, [TARGET, OTHER], TARGET,
                              fake_factory(events))
    assert not caught.value.rollback_incomplete
    assert registry.read_bytes() == original_registry
    assert load_store(store) == RAMALS
    assert all(path.read_bytes() == payload
               for path, payload in before_files.items())
    assert "register" in events


@pytest.mark.parametrize("kind", ["create", "remove"])
def test_registry_restore_error_sets_manual_reconciliation_flag(
    kind, tmp_path, monkeypatch
):
    if kind == "create":
        root, registry = environment(tmp_path)
        target = provision
        save_original = provision.save_tenants
    else:
        root, registry, store, _ = lab(tmp_path)
        target = removal
        save_original = removal.save_tenants

    def fail_late(path, records):
        save_original(path, records)
        raise OSError("save ended badly")

    def refuse_restore(*args):
        raise OSError("rollback disk failure")

    monkeypatch.setattr(target, "save_tenants", fail_late)
    monkeypatch.setattr(target, "restore_registry", refuse_restore)
    if kind == "create":
        with pytest.raises(provision.TenantProvisionError) as caught:
            provision.provision_tenant(
                root, registry, [], TENANT, *credentials(), make_factory([])
            )
    else:
        with pytest.raises(removal.TenantRemovalError) as caught:
            removal.remove_tenant(root, registry, store,
                                  [TARGET, OTHER], TARGET, fake_factory([]))
    assert caught.value.rollback_incomplete
