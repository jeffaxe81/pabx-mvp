#!/usr/bin/env python3
"""Servidor de provisioning mTLS SOMENTE para laboratorio no loopback.

Senhas SIP contidas nos .cfg nunca sao registradas em log. Certificados
clientes validos, com SHA256 explicitamente autorizado a UM MAC/tenant,
sao obrigatorios. Nao substitui homologacao em telefone fisico.
"""
import argparse
import errno
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import ssl
import stat
import time

MAX_JSON = 1024 * 1024
MAX_CFG = 512 * 1024
MAX_DEVICES = 5000
MAC_RE = re.compile(r"[0-9a-f]{12}\Z")
FINGERPRINT_RE = re.compile(r"[0-9a-f]{64}\Z")
TENANT_RE = re.compile(r"t[1-9][0-9]*\Z")
EXTENSION_RE = re.compile(r"(t[1-9][0-9]*)-[0-9]{3,6}\Z")
ROUTE_RE = re.compile(r"/([0-9a-f]{12})\.cfg\Z")


def unique_keys(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("chave JSON duplicada")
        result[name] = value
    return result


def read_json(path, *, private=False, dir_fd=None):
    # Validar e ler o MESMO inode, mesmo durante substituicao atomica.
    # O_NONBLOCK impede bloqueio se um pathname for trocado por FIFO.
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("leitura segura requer Linux/POSIX O_NOFOLLOW")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        fd = os.open(path, flags, dir_fd=dir_fd)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise ValueError("arquivo ausente ou link simbolico") from exc
        raise
    try:
        stats = os.fstat(fd)
        if not stat.S_ISREG(stats.st_mode):
            raise ValueError("arquivo JSON deve ser regular")
        if stats.st_size > MAX_JSON:
            raise ValueError("JSON excede limite")
        if private and stats.st_mode & 0o077:
            raise ValueError("permissoes inseguras do cadastro privado")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            content = stream.read(MAX_JSON + 1)
        if len(content) > MAX_JSON:
            raise ValueError("JSON excede limite")
        return json.loads(content.decode("utf-8"),
                          object_pairs_hook=unique_keys,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("constante JSON invalida")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("cadastro JSON invalido") from exc
    finally:
        os.close(fd)


def load_policy(registry_path, devices_path):
    """Vincula o certificado cliente ao MAC e ao tenant dos dados de origem."""
    registry = read_json(registry_path, private=True)
    devices = read_json(devices_path)
    return validate_policy(registry, devices)


def validate_policy(registry, devices):
    """Valida a mesma politica v2 na leitura HTTP e na administracao local."""
    if (not isinstance(registry, dict)
            or type(registry.get("schema_version")) is not int
            or registry["schema_version"] != 2):
        raise ValueError("schema do cadastro de certificados invalido")
    bindings = registry.get("devices")
    if not isinstance(bindings, list) or not 1 <= len(bindings) <= MAX_DEVICES:
        raise ValueError("cadastro de certificados vazio ou excedido")
    if not isinstance(devices, dict) or not isinstance(devices.get("devices"), list):
        raise ValueError("manifesto de telefones invalido")
    if len(devices["devices"]) > MAX_DEVICES:
        raise ValueError("manifesto de telefones excedido")

    manifest = {}
    for item in devices["devices"]:
        if not isinstance(item, dict):
            raise ValueError("item de telefone invalido")
        mac, extension = item.get("mac"), item.get("ramal")
        if not isinstance(mac, str) or not MAC_RE.fullmatch(mac):
            raise ValueError("MAC do telefone precisa ser lowercase")
        if mac in manifest:
            raise ValueError("MAC duplicado no manifesto")
        if not isinstance(extension, str) or not EXTENSION_RE.fullmatch(extension):
            raise ValueError("ramal sem tenant valido")
        manifest[mac] = (extension.split("-", 1)[0], item.get("vendor"))

    policy = {}
    fingerprints = set()
    for entry in bindings:
        if (not isinstance(entry, dict) or set(entry) != {
                "mac", "tenant", "client_sha256", "valid_from",
                "valid_until", "revoked"}):
            raise ValueError("vinculo de certificado invalido")
        mac, tenant, digest = entry["mac"], entry["tenant"], entry["client_sha256"]
        start, end, revoked = entry["valid_from"], entry["valid_until"], entry["revoked"]
        if (type(start) is not int or type(end) is not int
                or type(revoked) is not bool or start <= 0 or end <= start
                or end - start > 30 * 86400):
            raise ValueError("janela de validade ou revogacao invalida")
        if (not isinstance(mac, str) or not MAC_RE.fullmatch(mac)
                or not isinstance(tenant, str) or not TENANT_RE.fullmatch(tenant)
                or not isinstance(digest, str) or not FINGERPRINT_RE.fullmatch(digest)):
            raise ValueError("identificador de certificado/tenant/MAC invalido")
        if mac in policy or digest in fingerprints:
            raise ValueError("certificado ou MAC duplicado no cadastro")
        if manifest.get(mac) != (tenant, "yealink"):
            raise ValueError("vinculo MAC/tenant diverge da fonte de provisionamento")
        fingerprints.add(digest)
        policy[mac] = (digest, start, end, revoked)
    return policy


def authorized(policy, mac, client_der, *, now=None):
    """Validade/revogacao rechecadas no instante de cada consulta."""
    if (not isinstance(mac, str) or not MAC_RE.fullmatch(mac)
            or not isinstance(client_der, bytes) or not client_der):
        return False
    claim = policy.get(mac)
    if claim is None:
        return False
    digest, start, end, revoked = claim
    moment = time.time() if now is None else now
    if (type(moment) not in (int, float) or not (start <= moment < end)
            or revoked):
        return False
    from hmac import compare_digest
    return compare_digest(digest, hashlib.sha256(client_der).hexdigest())


def read_cfg(directory, mac):
    """Le somente arquivo regular pelo dirfd, rejeitando symlink e travessia."""
    if not isinstance(mac, str) or not MAC_RE.fullmatch(mac):
        raise ValueError("MAC invalido")
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("diretorio de configuracoes invalido")
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("leitura segura requer Linux/POSIX O_NOFOLLOW")
    root_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0)
    root_fd = os.open(directory, root_flags)
    try:
        root = os.fstat(root_fd)
        if root.st_mode & 0o077 or root.st_uid != os.geteuid():
            raise ValueError("diretorio de configuracoes deve ser privado e do servico")
        fd = os.open(mac + ".cfg", file_flags, dir_fd=root_fd)
        try:
            stats = os.fstat(fd)
            if (not stat.S_ISREG(stats.st_mode) or stats.st_size > MAX_CFG
                    or stats.st_mode & 0o077 or stats.st_uid != os.geteuid()
                    or stats.st_nlink != 1):
                raise ValueError("configuracao de aparelho invalida")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                content = stream.read(MAX_CFG + 1)
            if len(content) > MAX_CFG:
                raise ValueError("configuracao excede limite")
            return content
        finally:
            os.close(fd)
    finally:
        os.close(root_fd)


class ProvisioningHandler(BaseHTTPRequestHandler):
    server_version = "AXE-PV-LAB"
    sys_version = ""

    def log_message(self, format, *args):
        # URLs, certificados, IPs e credenciais nao entram em logs de acesso.
        pass

    def _respond(self, code, data=b""):
        self.send_response(code)
        self.send_header("Cache-Control", "no-store, private, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if data:
            self.wfile.write(data)

    def do_GET(self):
        route = ROUTE_RE.fullmatch(self.path)
        if route is None:
            return self._respond(404)
        mac = route.group(1)
        # ssl.wrap_socket() com CERT_REQUIRED rejeita o cliente ANTES
        # da requisicao HTTP se nao apresentar certificado assinado pela CA.
        try:
            cert = self.connection.getpeercert(binary_form=True)
            # Revogacao em arquivo passa a valer no proximo GET, sem restart.
            # Problema de leitura/cadastro invalido falha fechado, sem cfg.
            policy = load_policy(self.server.registry_path, self.server.devices_path)
            if not authorized(policy, mac, cert):
                return self._respond(404)
            content = read_cfg(self.server.config_dir, mac)
        except (ValueError, OSError, TypeError):
            return self._respond(404)
        self._respond(200, content)

    def do_HEAD(self):
        self._respond(405)

    def do_POST(self):
        self._respond(405)

    def do_PUT(self):
        self._respond(405)

    def do_DELETE(self):
        self._respond(405)


def serve(registry_path, devices_path, config_dir, cert_path, key_path, ca_path, *, port=8443):
    """Sempre em 127.0.0.1, sem porta publica, sem carregamento de Docker."""
    for path in (cert_path, key_path, ca_path):
        path = Path(path)
        if path.is_symlink() or not path.is_file():
            raise ValueError("certificado/chave ausente ou link simbolico")
    if os.name == "posix" and Path(key_path).stat().st_mode & 0o077:
        raise ValueError("chave TLS deve ser privada (0600)")
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("porta invalida")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_cert_chain(str(cert_path), str(key_path))
    context.load_verify_locations(cafile=str(ca_path))
    context.options |= getattr(ssl, "OP_NO_COMPRESSION", 0)
    server = ThreadingHTTPServer(("127.0.0.1", port), ProvisioningHandler)
    server.daemon_threads = True
    server.registry_path = str(registry_path)
    server.devices_path = str(devices_path)
    server.config_dir = str(config_dir)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True,
                        help="JSON privado mode 0600: tenant, MAC, SHA256 DER do cliente")
    parser.add_argument("--devices", type=Path, required=True)
    parser.add_argument("--files", type=Path, required=True)
    parser.add_argument("--server-cert", type=Path, required=True)
    parser.add_argument("--server-key", type=Path, required=True)
    parser.add_argument("--client-ca", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8443)
    args = parser.parse_args(argv)
    try:
        load_policy(args.registry, args.devices)  # startup fail-closed
        serve(args.registry, args.devices, args.files, args.server_cert,
              args.server_key, args.client_ca, port=args.port)
    except (ValueError, OSError, ssl.SSLError) as exc:
        parser.exit(2, "Provisionamento mTLS bloqueado: " + type(exc).__name__ + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
