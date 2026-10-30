"""Criação recuperável de tenant: arquivos, AstDB, reload e registro.

Nenhuma transação distribuída existe entre Asterisk e JSON. Em falhas,
o serviço remove os arquivos novos e tenta compensar o AstDB.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import tempfile
import threading

from conf_generator import render_all
from tenant_config_invariants import validate_generated_tenant_files
from tenant_registry_recovery import snapshot_registry, restore_registry
from tenants import (
    render_tenant_pjsip, render_tenant_queues, render_tenant_extensions,
    render_tenant_voicemail, render_tenant_parking, save_tenants,
)

TENANT_TRANSACTION_LOCK = threading.RLock()
RELOAD_COMPONENTS = ("pjsip", "dialplan", "voicemail", "queue", "parking")


class TenantProvisionError(RuntimeError):
    def __init__(self, rollback_incomplete=False):
        super().__init__("provisionamento do tenant não foi concluído")
        self.rollback_incomplete = rollback_incomplete


def build_tenant_files(root, tenant_id, sip_credentials, voicemail_pins):
    root = Path(root)
    contents = {
        root / "pjsip_tenants" / f"{tenant_id}.conf": render_tenant_pjsip(tenant_id, sip_credentials),
        root / "queues_tenants" / f"{tenant_id}.conf": render_tenant_queues(tenant_id),
        root / "extensions_tenants" / f"{tenant_id}.conf": render_tenant_extensions(tenant_id),
        root / "voicemail_tenants" / f"{tenant_id}.conf": render_tenant_voicemail(tenant_id, voicemail_pins),
        root / "parking_tenants" / f"{tenant_id}.conf": render_tenant_parking(tenant_id),
    }
    empty_files = render_all([], tenant_ids={tenant_id})
    for suffix in (
        f"extensions_dynamic_dial-{tenant_id}.conf",
        f"extensions_dynamic_hints-{tenant_id}.conf",
        f"voicemail_dynamic_{tenant_id}.conf",
    ):
        contents[root / "generated" / suffix] = empty_files[suffix]
    # Falhar antes de criar arquivos/registrar DID no AstDB.
    validate_generated_tenant_files(contents, tenant_id)
    return contents


@contextmanager
def exclusive_tenant_files(contents):
    """Cria arquivos apenas se inexistentes; remove-os se o chamador falhar.

    Os conteúdos são escritos e sincronizados antes da publicação.
    os.link publica sem substituir um .conf existente e exige que o
    temporário esteja no mesmo filesystem do arquivo final.
    """
    if not isinstance(contents, dict) or not contents:
        raise ValueError("configurações do tenant inválidas")
    staged = []
    published = []
    try:
        for path, text in contents.items():
            target = Path(path)
            if target.suffix != ".conf" or not isinstance(text, str):
                raise ValueError("configuração de tenant inválida")
            if not target.parent.is_dir() or target.parent.is_symlink():
                raise ValueError("diretório de tenant ausente ou inseguro")
            if target.exists() or target.is_symlink():
                raise FileExistsError("configuração de tenant já existente")
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix=".tenant-stage-", dir=target.parent, delete=False
            ) as file:
                temporary = Path(file.name)
                staged.append(temporary)
                os.fchmod(file.fileno(), 0o644)
                file.write(text.encode("utf-8"))
                file.flush()
                os.fsync(file.fileno())
            staged[-1] = (temporary, target)
        for temporary, target in staged:
            os.link(temporary, target)
            published.append(target)
        yield
    except BaseException:
        for target in reversed(published):
            target.unlink(missing_ok=True)
        raise
    finally:
        for item in staged:
            temporary = item[0] if isinstance(item, tuple) else item
            temporary.unlink(missing_ok=True)


def provision_tenant(root, registry_path, existing, cleaned, sip_credentials, voicemail_pins, client_factory):
    """Confirma o tenant somente após o reload e save do registro.

    Compensação via AMI é melhor esforço: retorna status específico
    quando a reversão do DID ou runtime não pôde ser confirmada.
    """
    config_files = build_tenant_files(root, cleaned["tenant_id"], sip_credentials, voicemail_pins)
    attempted_did = False
    registry_save_started = False
    registry_snapshot = None
    client = None
    try:
        registry_snapshot = snapshot_registry(registry_path)
        with exclusive_tenant_files(config_files):
            client = client_factory()
            client.connect_and_login()
            attempted_did = True
            client.register_tenant_did(cleaned["did"], cleaned["tenant_id"])
            reload_result = client.reload_pjsip_and_dialplan()
            if not isinstance(reload_result, dict) or any(
                reload_result.get(name) not in ("Success", "Follows")
                for name in RELOAD_COMPONENTS
            ):
                raise RuntimeError("AMI não confirmou as recargas")
            registry_save_started = True
            save_tenants(registry_path, [*existing, cleaned])
        return reload_result
    except Exception as original_error:
        # Os arquivos gerados já foram removidos pelo context manager.
        # A rede pode falhar após o AstDB ter aplicado o DBPut.
        rollback_incomplete = False
        if registry_save_started:
            try:
                restore_registry(registry_path, registry_snapshot)
            except (OSError, ValueError):
                rollback_incomplete = True
        if attempted_did:
            try:
                # Uma falha de rede pode invalidar o socket original.
                # A compensação usa uma conexão independente.
                if client is not None:
                    client.close()
                client = client_factory()
                client.connect_and_login()
                client.unregister_tenant_did(cleaned["did"])
                compensating_reload = client.reload_pjsip_and_dialplan()
                if not isinstance(compensating_reload, dict) or any(
                    compensating_reload.get(name) not in ("Success", "Follows")
                    for name in RELOAD_COMPONENTS
                ):
                    rollback_incomplete = True
            except Exception:
                rollback_incomplete = True
        raise TenantProvisionError(rollback_incomplete) from original_error
    finally:
        if client is not None:
            client.close()
