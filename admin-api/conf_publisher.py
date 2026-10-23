"""Publicação recuperável de arquivos dinâmicos do Asterisk.

Substituição atômica por arquivo; em erro, restaura os snapshots
anteriores. Não é transação multi-arquivo ou AMI/AstDB distribuída.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import re
import stat
import tempfile

_SAFE_CONF = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\.conf\Z")


def _write_staged(directory: Path, data: bytes, mode: int) -> Path:
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".pabx-conf-", dir=directory, delete=False
        ) as handle:
            temp_path = Path(handle.name)
            os.fchmod(handle.fileno(), mode)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        return temp_path
    except BaseException:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise


def _restore_snapshot(target: Path, previous):
    """Snapshot (bytes, mode) ou None quando arquivo não existia."""
    if previous is None:
        target.unlink(missing_ok=True)
        return
    contents, mode = previous
    temp = _write_staged(target.parent, contents, mode)
    try:
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)


@contextmanager
def published_conf_batch(directory, generated: dict):
    """Publica arquivos e reverte o lote se o chamador lançar erro.

    Antes de substituir qualquer destino, prepara todos os novos
    conteúdos na mesma pasta. Asterisk pode observar uma mistura
    transitória durante a publicação: use uma única instância escritora
    e execute reload só após o lote completo.
    """
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("diretório de configuração inválido")
    if not isinstance(generated, dict):
        raise ValueError("lote de configuração inválido")

    snapshots = {}
    staged = {}
    published = []
    try:
        for filename, content in generated.items():
            if not isinstance(filename, str) or not _SAFE_CONF.fullmatch(filename):
                raise ValueError("nome de arquivo de configuração inválido")
            if not isinstance(content, str):
                raise ValueError("conteúdo de configuração inválido")
            target = root / filename
            if target.is_symlink():
                raise ValueError(f"arquivo de configuração é link simbólico: {filename}")
            if target.exists():
                mode_bits = target.stat().st_mode
                if not stat.S_ISREG(mode_bits):
                    raise ValueError(f"arquivo de configuração não regular: {filename}")
                # Preserva acesso do serviço Asterisk ao arquivo.
                mode = stat.S_IMODE(mode_bits)
                snapshots[filename] = (target.read_bytes(), mode)
            else:
                mode = 0o644
                snapshots[filename] = None
            staged[filename] = _write_staged(root, content.encode("utf-8"), mode)

        for filename, temp in staged.items():
            os.replace(temp, root / filename)
            published.append(filename)
        yield
    except BaseException as failure:
        rollback_errors = []
        for filename in reversed(published):
            try:
                _restore_snapshot(root / filename, snapshots[filename])
            except OSError as exc:
                rollback_errors.append(f"{filename}: {type(exc).__name__}")
        if rollback_errors:
            raise RuntimeError(
                "rollback de configurações incompleto: " + ", ".join(rollback_errors)
            ) from failure
        raise
    finally:
        for temp in staged.values():
            temp.unlink(missing_ok=True)
