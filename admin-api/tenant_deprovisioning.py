"""Remoção compensável de tenant e seus ramais, sem transação distribuída."""
from contextlib import contextmanager
from pathlib import Path
import re
import stat

from conf_publisher import published_conf_batch, _restore_snapshot
from conf_generator import render_pjsip_dynamic
from store import load_store, save_store
from tenants import save_tenants
from tenant_provisioning import RELOAD_COMPONENTS
from tenant_registry_recovery import snapshot_registry, restore_registry


_SAFE_TENANT_ID = re.compile(r"t[1-9][0-9]*\Z")


class TenantRemovalError(RuntimeError):
    def __init__(self, rollback_incomplete=False):
        super().__init__("remoção do tenant não foi concluída")
        self.rollback_incomplete = rollback_incomplete


class FileRestoreError(RuntimeError):
    pass


def tenant_config_paths(root, tenant_id):
    if (not isinstance(tenant_id, str)
            or _SAFE_TENANT_ID.fullmatch(tenant_id) is None
            or len(tenant_id) > 32):
        raise ValueError("tenant inválido para desprovisionamento")
    root = Path(root)
    return [
        *(root / subdir / f"{tenant_id}.conf" for subdir in (
            "pjsip_tenants", "queues_tenants", "extensions_tenants",
            "voicemail_tenants", "parking_tenants",
        )),
        *(root / "generated" / name for name in (
            f"extensions_dynamic_dial-{tenant_id}.conf",
            f"extensions_dynamic_hints-{tenant_id}.conf",
            f"voicemail_dynamic_{tenant_id}.conf",
        )),
    ]


@contextmanager
def retired_config_files(paths):
    """Remove somente depois de salvar snapshots; restaura em falha."""
    snapshots = {}
    for path in paths:
        file = Path(path)
        if file.is_symlink() or not file.is_file() or file.parent.is_symlink():
            raise ValueError("configuração do tenant ausente ou insegura")
        metadata = file.stat()
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("configuração do tenant não regular")
        snapshots[file] = (file.read_bytes(), stat.S_IMODE(metadata.st_mode))
    retired = []
    try:
        for file in snapshots:
            file.unlink()
            retired.append(file)
        yield
    except BaseException as exc:
        problems = []
        for file in reversed(retired):
            try:
                _restore_snapshot(file, snapshots[file])
            except OSError:
                problems.append(file.name)
        if problems:
            raise FileRestoreError("restauração de arquivos incompleta") from exc
        raise


def remove_tenant(root, registry_path, store_path, existing, record, client_factory):
    """Exclui arquivos e registros, ou tenta desfazer alterações."""
    root = Path(root)
    old_extensions = load_store(store_path)
    remaining_extensions = [
        item for item in old_extensions
        if item.get("tenant", "t1") != record["tenant_id"]
    ]
    removed_count = len(old_extensions) - len(remaining_extensions)
    remaining_tenants = [
        tenant for tenant in existing if tenant["tenant_id"] != record["tenant_id"]
    ]
    did_attempted = False
    store_touched = False
    registry_save_started = False
    registry_snapshot = None
    client = None
    try:
        registry_snapshot = snapshot_registry(registry_path)
        with retired_config_files(tenant_config_paths(root, record["tenant_id"])):
            with published_conf_batch(root / "generated", {
                "pjsip_dynamic.conf": render_pjsip_dynamic(remaining_extensions),
            }):
                client = client_factory()
                client.connect_and_login()
                did_attempted = True
                client.unregister_tenant_did(record["did"])
                reload_result = client.reload_pjsip_and_dialplan()
                if not isinstance(reload_result, dict) or any(
                    reload_result.get(name) not in ("Follows", "Success")
                    for name in RELOAD_COMPONENTS
                ):
                    raise RuntimeError("recarga Asterisk não confirmada")
                if removed_count:
                    store_touched = True
                    save_store(store_path, remaining_extensions)
                registry_save_started = True
                save_tenants(registry_path, remaining_tenants)
        return {"removed_extensions": removed_count, "reload": reload_result}
    except Exception as exc:
        rollback_incomplete = isinstance(exc, FileRestoreError)
        if registry_save_started:
            try:
                restore_registry(registry_path, registry_snapshot)
            except (OSError, ValueError):
                rollback_incomplete = True
        if store_touched:
            try:
                save_store(store_path, old_extensions)
            except Exception:
                rollback_incomplete = True
        if did_attempted:
            try:
                if client is not None:
                    client.close()
                client = client_factory()
                client.connect_and_login()
                client.register_tenant_did(record["did"], record["tenant_id"])
                reload_previous = client.reload_pjsip_and_dialplan()
                if not isinstance(reload_previous, dict) or any(
                    reload_previous.get(name) not in ("Follows", "Success")
                    for name in RELOAD_COMPONENTS
                ):
                    rollback_incomplete = True
            except Exception:
                rollback_incomplete = True
        raise TenantRemovalError(rollback_incomplete) from exc
    finally:
        if client is not None:
            client.close()
