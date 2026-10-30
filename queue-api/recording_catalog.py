"""Importação assistida de gravações com proveniência explicitamente atestada.

O utilitário NÃO descobre o tenant por nome, DID ou caller ID. O operador
deve fornecer um manifesto confiável e executar --apply explicitamente.
"""
import argparse
import fcntl
import json
import os
import re
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path
from recordings import _recording_directory_fd

from recording_access import (
    MAX_POLICY_BYTES, TENANT, _valid_filename, load_recording_policy,
    _reject_duplicate_json_keys, read_regular_file_secure,
)

MAX_IMPORT_BYTES = 1024 * 1024
MAX_IMPORT_ROWS = 1000
SOURCE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{3,99}$")
EXTENSION = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")


def load_manifest(path):
    """Importação JSONL com esquema estrito e sem campos desconhecidos."""
    raw = read_regular_file_secure(path, MAX_IMPORT_BYTES)
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise ValueError("manifesto não é UTF-8") from exc
    if not lines or len(lines) > MAX_IMPORT_ROWS:
        raise ValueError("manifesto vazio ou excede o limite de registros")
    records = []
    seen = set()
    ref_tenants = {}
    ref_files = {}
    for number, line in enumerate(lines, start=1):
        try:
            row = json.loads(
                line, object_pairs_hook=_reject_duplicate_json_keys,
                parse_constant=lambda _: (_ for _ in ()).throw(
                    ValueError("número JSON não finito")),
            )
        except ValueError as exc:
            raise ValueError(f"JSON inválido na linha {number}") from exc
        if not isinstance(row, dict) or not {"filename", "tenant", "source_ref"} <= row.keys():
            raise ValueError(f"campos obrigatórios ausentes na linha {number}")
        if not row.keys() <= {"filename", "tenant", "source_ref", "owner_extension"}:
            raise ValueError(f"campo não reconhecido na linha {number}")
        filename, tenant, ref = row["filename"], row["tenant"], row["source_ref"]
        if not _valid_filename(filename):
            raise ValueError(f"nome inseguro na linha {number}")
        if not isinstance(tenant, str) or not TENANT.fullmatch(tenant):
            raise ValueError(f"tenant inválido na linha {number}")
        if not isinstance(ref, str) or not SOURCE_REF.fullmatch(ref):
            raise ValueError(f"referência de evidência inválida na linha {number}")
        owner = row.get("owner_extension")
        if owner is not None and (
            not isinstance(owner, str) or not EXTENSION.fullmatch(owner)
            or not owner.startswith(tenant + "-")
        ):
            raise ValueError(f"ramal de outra empresa ou inválido na linha {number}")
        if ref in ref_tenants and ref_tenants[ref] != tenant:
            raise ValueError(f"referência de origem compartilhada entre empresas, linha {number}")
        ref_tenants[ref] = tenant
        if ref in ref_files and ref_files[ref] != filename:
            raise ValueError(f"evidência compartilhada por gravações distintas, linha {number}")
        ref_files[ref] = filename
        if filename in seen:
            raise ValueError(f"arquivo repetido no manifesto, linha {number}")
        seen.add(filename)
        records.append(row)
    return records


def read_policy_secure(path):
    """Recusa caminho simbólico, permissões abertas e catálogo malformado."""
    path = Path(path)
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_IMODE(info.st_mode) & 0o077
        or info.st_size > MAX_POLICY_BYTES
    ):
        raise ValueError("política deve ser arquivo regular privado (modo 0600)")
    policy = load_recording_policy(path)
    if policy is None:
        raise ValueError("política de gravações inválida ou ausente")
    return policy


def preview_batch(policy, rows, directory):
    """Não sobrescreve classificação existente. Falha antes de qualquer escrita."""
    directory_fd = _recording_directory_fd(directory)
    if directory_fd is None:
        raise ValueError("diretório de gravações inválido")
    try:
        for row in rows:
            filename = row["filename"]
            if not _valid_filename(filename):
                raise ValueError("nome de gravação inválido")
            try:
                info = os.stat(filename, dir_fd=directory_fd, follow_symlinks=False)
            except (OSError, TypeError, ValueError) as exc:
                raise ValueError("gravação não encontrada ou link simbólico") from exc
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                # Hardlinks permitem que dois nomes apontem para a mesma
                # mídia, tornando ambígua a classificação por arquivo.
                raise ValueError("gravação não regular ou com múltiplos links")
    finally:
        os.close(directory_fd)
    updated = dict(policy)
    recordings = dict(policy["recordings"])
    # Provas de origem são globais ao catálogo, não apenas ao lote de
    # importação. Evita associar a mesma chamada a t1 e t10 em lotes diferentes.
    ref_tenants = {}
    ref_files = {}
    for existing_filename, metadata in recordings.items():
        ref = metadata.get("source_ref")
        if ref is None:
            continue
        prior = ref_tenants.setdefault(ref, metadata["tenant"])
        if prior != metadata["tenant"]:
            raise ValueError("catálogo com origem compartilhada entre empresas")
        if ref in ref_files and ref_files[ref] != existing_filename:
            raise ValueError("origem compartilhada por mais de uma gravação")
        ref_files[ref] = existing_filename
    created = unchanged = 0
    for row in rows:
        filename = row["filename"]
        previous_tenant = ref_tenants.setdefault(row["source_ref"], row["tenant"])
        if previous_tenant != row["tenant"]:
            raise ValueError("origem compartilhada entre empresas em lotes distintos")
        if row["source_ref"] in ref_files and ref_files[row["source_ref"]] != filename:
            raise ValueError("mesma prova de origem usada em arquivos distintos")
        ref_files[row["source_ref"]] = filename
        metadata = {
            "tenant": row["tenant"],
            "source_ref": row["source_ref"],
        }
        if "owner_extension" in row:
            metadata["owner_extension"] = row["owner_extension"]
        previous = recordings.get(filename)
        if previous is not None:
            if previous != metadata:
                raise ValueError("classificação já existe e difere: " + filename)
            unchanged += 1
        else:
            recordings[filename] = metadata
            created += 1
    updated["recordings"] = recordings
    encoded = (json.dumps(updated, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if len(encoded) > MAX_POLICY_BYTES:
        raise ValueError("resultado ultrapassa o tamanho máximo da política")
    return updated, encoded, {"new": created, "unchanged": unchanged, "total": len(rows)}


@contextmanager
def policy_lock(path):
    """Lock em inode estável, inclusive entre processos CLI concorrentes."""
    lock = str(path) + ".lock"
    flags = (os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
             | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NONBLOCK", 0))
    fd = os.open(lock, flags, 0o600)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise ValueError("lock do catálogo possui inode ou permissões inseguras")
        with os.fdopen(fd, "r+b") as handle:
            fd = -1
            fcntl.flock(handle, fcntl.LOCK_EX)
            yield
            fcntl.flock(handle, fcntl.LOCK_UN)
    finally:
        if fd >= 0:
            os.close(fd)


def atomic_save(path, encoded):
    path = Path(path)
    descriptor, temp = tempfile.mkstemp(prefix=".recordings-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as file:
            os.fchmod(file.fileno(), 0o600)
            file.write(encoded)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def reconcile_catalog(policy_path, recordings_dir, manifest_path, apply=False):
    rows = load_manifest(manifest_path)
    if not apply:
        policy = read_policy_secure(policy_path)
        _, _, summary = preview_batch(policy, rows, recordings_dir)
        return {"mode": "dry-run", **summary}

    with policy_lock(policy_path):
        policy = read_policy_secure(policy_path)
        _, encoded, summary = preview_batch(policy, rows, recordings_dir)
        if summary["new"]:
            atomic_save(policy_path, encoded)
    return {"mode": "applied", **summary}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Catálogo auditável de gravações por tenant")
    parser.add_argument("--policy", required=True)
    parser.add_argument("--recordings-dir", required=True)
    parser.add_argument("--manifest", required=True, help="JSONL com evidências conferidas")
    parser.add_argument("--apply", action="store_true", help="sem esta opção, somente simula")
    args = parser.parse_args(argv)
    try:
        report = reconcile_catalog(args.policy, args.recordings_dir, args.manifest, args.apply)
    except (OSError, ValueError) as exc:
        parser.exit(2, "Importação recusada: " + str(exc) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
