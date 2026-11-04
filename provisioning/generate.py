#!/usr/bin/env python3
"""Provisionamento IP com validacao previa e publicacao atomica.

Arquivos .cfg contem credenciais SIP. A distribuicao HTTP deve ter
controles proprios de autenticacao/rede; esta rotina nao os implementa.
"""
import json
import os
import re
import secrets
import stat
from pathlib import Path

BASE = os.path.dirname(os.path.abspath(__file__))
DEVICES_FILE = os.path.join(BASE, "devices.json")
TEMPLATES_DIR = os.path.join(BASE, "templates")
OUTPUT_DIR = os.path.join(BASE, "files")
TEMPLATE_EXT = {"yealink": "yealink.cfg.tpl"}
REQUIRED = ("ramal", "nome", "senha", "servidor")
TOKENS = {"ramal": "{{RAMAL}}", "nome": "{{NOME}}",
          "senha": "{{SENHA}}", "servidor": "{{SERVIDOR}}"}
LIMITS = {"ramal": 64, "nome": 128, "senha": 256, "servidor": 253}
MAX_DEVICES = 5000
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_TEMPLATE_BYTES = 256 * 1024
MAX_RENDERED_BYTES = 512 * 1024
TOKEN_PATTERN = re.compile(r"{{[^{}]*}}")
MAC_PATTERN = re.compile(r"[0-9a-fA-F]{12}\Z")


def _catalog():
    source = Path(DEVICES_FILE)
    if source.is_symlink() or not source.is_file():
        raise ValueError("PV-01: catalogo indisponivel ou link simbolico")
    if source.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("PV-02: catalogo excede limite")
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("PV-03: catalogo JSON invalido") from exc
    if not isinstance(data, dict):
        raise ValueError("PV-04: raiz do catalogo deve ser objeto")
    if "devices" not in data:
        raise ValueError("PV-05: devices ausente")
    devices = data["devices"]
    if not isinstance(devices, list):
        raise ValueError("PV-06: devices deve ser lista")
    if len(devices) > MAX_DEVICES:
        raise ValueError("PV-07: numero de dispositivos excede limite")
    return devices


def _validate(devices):
    seen = set()
    supported = []
    for device in devices:
        if not isinstance(device, dict):
            raise ValueError("PV-08: registro nao e objeto")
        if "mac" not in device:
            raise ValueError("PV-09: MAC ausente")
        mac = device["mac"]
        if not isinstance(mac, str):
            raise ValueError("PV-10: MAC deve ser texto")
        if not MAC_PATTERN.fullmatch(mac):
            raise ValueError("PV-11: MAC invalido")
        normalized = mac.lower()
        if normalized in seen:
            raise ValueError("PV-12: MAC duplicado")
        seen.add(normalized)
        if "vendor" not in device:
            raise ValueError("PV-13: fabricante ausente")
        vendor = device["vendor"]
        if not isinstance(vendor, str):
            raise ValueError("PV-14: fabricante deve ser texto")
        if not vendor.strip():
            raise ValueError("PV-15: fabricante vazio")
        if vendor not in TEMPLATE_EXT:
            print(f"[AVISO] fabricante nao suportado, ignorando MAC {mac}")
            continue
        for field, code in zip(REQUIRED, ("PV-16", "PV-17", "PV-18", "PV-19")):
            if field not in device:
                raise ValueError(f"{code}: campo obrigatorio ausente")
        for field in REQUIRED:
            value = device[field]
            if not isinstance(value, str):
                raise ValueError("PV-20: campo de configuracao deve ser texto")
            if not value.strip():
                raise ValueError("PV-21: campo de configuracao vazio")
            if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
                raise ValueError("PV-22: caractere de controle na configuracao")
            if "{{" in value or "}}" in value:
                raise ValueError("PV-23: marcador de template em entrada")
            if len(value) > LIMITS[field]:
                raise ValueError("PV-24: campo excede limite")
        supported.append(device)
    return supported


def _template(vendor):
    path = Path(TEMPLATES_DIR) / TEMPLATE_EXT[vendor]
    if path.is_symlink() or not path.is_file():
        raise ValueError("PV-25: template indisponivel ou link simbolico")
    if path.stat().st_size > MAX_TEMPLATE_BYTES:
        raise ValueError("PV-26: template excede limite")
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeError as exc:
        raise ValueError("PV-27: codificacao do template invalida") from exc
    if any(token not in content for token in TOKENS.values()):
        raise ValueError("PV-28: template incompleto")
    if set(TOKEN_PATTERN.findall(content)) - set(TOKENS.values()):
        raise ValueError("PV-29: template possui marcador desconhecido")
    return content


def _stage(devices):
    templates = {}
    staged = []
    for device in devices:
        vendor = device["vendor"]
        if vendor not in templates:
            templates[vendor] = _template(vendor)
        rendered = templates[vendor]
        for field, token in TOKENS.items():
            rendered = rendered.replace(token, device[field])
        if "{{" in rendered or "}}" in rendered:
            raise ValueError("PV-29: marcador residual no template")
        data = rendered.encode("utf-8")
        if len(data) > MAX_RENDERED_BYTES:
            raise ValueError("PV-26: configuracao excede limite")
        staged.append((device["mac"].lower() + ".cfg", data))
    return staged


def _publish(staged):
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("PV-30: publicacao privada requer Linux/POSIX")
    import fcntl
    output = Path(OUTPUT_DIR)
    if output.is_symlink() or (output.exists() and not output.is_dir()):
        raise ValueError("PV-30: destino invalido ou link simbolico")
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    root_fd = os.open(output, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if os.fstat(root_fd).st_uid != os.geteuid():
            raise ValueError("PV-30: diretorio deve pertencer ao operador")
        # O inode do diretorio e estavel durante renomeacoes; escritores
        # cooperantes se serializam sem um lockfile substituivel.
        fcntl.flock(root_fd, fcntl.LOCK_EX)
        with os.scandir(root_fd) as entries:
            existing = [entry.name for entry in entries if entry.name.endswith(".cfg")]
        # Validar TODO o legado antes de restringir permissoes/publicar.
        for filename in existing:
            info = os.stat(filename, dir_fd=root_fd, follow_symlinks=False)
            if (not MAC_PATTERN.fullmatch(filename[:-4])
                    or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or info.st_uid != os.geteuid()):
                raise ValueError("PV-30: configuracao existente insegura")
        os.fchmod(root_fd, 0o700)
        for filename in existing:
            fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root_fd)
            try:
                info = os.fstat(fd)
                if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                        or info.st_uid != os.geteuid()):
                    raise ValueError("PV-30: configuracao existente insegura")
                os.fchmod(fd, 0o600)
                os.fsync(fd)
            finally:
                os.close(fd)
        for filename, data in staged:
            temporary = ".axe-pv-" + secrets.token_hex(12) + ".tmp"
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=root_fd)
            try:
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, "wb", closefd=False) as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(fd)
                os.replace(temporary, filename, src_dir_fd=root_fd, dst_dir_fd=root_fd)
            finally:
                os.close(fd)
                try:
                    os.unlink(temporary, dir_fd=root_fd)
                except FileNotFoundError:
                    pass
            print(f"[OK] gerado: {filename}")
        os.fsync(root_fd)
    finally:
        os.close(root_fd)  # tambem libera flock, inclusive em falhas.


def main():
    staged = _stage(_validate(_catalog()))
    _publish(staged)


if __name__ == "__main__":
    main()
