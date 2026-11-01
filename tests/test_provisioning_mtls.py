"""mTLS provisioning: certificado unico, empresa/MAC e arquivo sem fuga."""
import hashlib
from http.server import ThreadingHTTPServer
import io
import json
from pathlib import Path
import shutil
import ssl
import subprocess
import threading
import time
from types import SimpleNamespace
import urllib.error
import urllib.request

import pytest

from provisioning import mtls_server as pv


MAC1 = "aabbccddeeff"
MAC2 = "001122334455"
CLIENT1 = b"lab-certificate-t1"
CLIENT2 = b"lab-certificate-t2"


def config(tmp_path):
    cert_registry = tmp_path / "private-registry.json"
    device_registry = tmp_path / "devices.json"
    folder = tmp_path / "cfg"
    folder.mkdir()
    now = int(time.time())
    cert_registry.write_text(json.dumps({"schema_version": 2, "devices": [
        {"mac": MAC1, "tenant": "t1", "client_sha256": hashlib.sha256(CLIENT1).hexdigest(),
         "valid_from": now - 60, "valid_until": now + 3600, "revoked": False},
        {"mac": MAC2, "tenant": "t2", "client_sha256": hashlib.sha256(CLIENT2).hexdigest(),
         "valid_from": now - 60, "valid_until": now + 3600, "revoked": False},
    ]}), encoding="utf-8")
    cert_registry.chmod(0o600)
    device_registry.write_text(json.dumps({"devices": [
        {"mac": MAC1, "vendor": "yealink", "ramal": "t1-1001"},
        {"mac": MAC2, "vendor": "yealink", "ramal": "t2-1001"},
    ]}), encoding="utf-8")
    (folder / (MAC1 + ".cfg")).write_bytes(b"user=t1-1001\npassword=secret-t1")
    (folder / (MAC2 + ".cfg")).write_bytes(b"user=t2-1001\npassword=secret-t2")
    return cert_registry, device_registry, folder


def test_mtls_politica_isola_tenant_e_mac(tmp_path):
    registry, devices, _ = config(tmp_path)
    policy = pv.load_policy(registry, devices)
    assert len(policy) == 2
    assert pv.authorized(policy, MAC1, CLIENT1)
    assert pv.authorized(policy, MAC2, CLIENT2)
    assert not pv.authorized(policy, MAC1, CLIENT2)
    assert not pv.authorized(policy, MAC2, CLIENT1)
    assert not pv.authorized(policy, MAC1, b"outro")
    assert not pv.authorized(policy, MAC1, None)


@pytest.mark.parametrize("item,field,value", [
    (0, "tenant", "t2"),
    (1, "mac", MAC1),
    (0, "client_sha256", hashlib.sha256(CLIENT2).hexdigest()),
    (0, "client_sha256", "A" * 64),
    (0, "mac", "aabbccddZZZZ"),
    (0, "tenant", "t0"),
    (0, "client_sha256", "abc"),
])
def test_rejeita_cadastro_divergente_ou_duplicado(tmp_path, item, field, value):
    registry, devices, _ = config(tmp_path)
    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["devices"][item][field] = value
    registry.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        pv.load_policy(registry, devices)


@pytest.mark.parametrize("bad", [
    {"devices": []},
    {"schema_version": 0, "devices": []},
    {"schema_version": 2, "devices": "nao e lista"},
    {"schema_version": 2, "devices": [{"tenant": "t1", "mac": MAC1}]},
])
def test_cadastro_incompleto_falha_fechado(tmp_path, bad):
    registry, devices, _ = config(tmp_path)
    registry.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError):
        pv.load_policy(registry, devices)


def test_rejeita_permissoes_publicas_do_cadastro_privado(tmp_path):
    registry, devices, _ = config(tmp_path)
    registry.chmod(0o644)
    with pytest.raises(ValueError, match="permissoes inseguras"):
        pv.load_policy(registry, devices)


def test_rejeita_json_com_chaves_repetidas_e_symlink(tmp_path):
    registry, devices, _ = config(tmp_path)
    registry.write_text('{"schema_version":2,"schema_version":2,"devices":[]}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicada"):
        pv.load_policy(registry, devices)
    registry.unlink()
    registry.symlink_to(devices)
    with pytest.raises(ValueError, match="link simbolico"):
        pv.load_policy(registry, devices)


def test_registro_nao_confunde_empresa_com_nome_similar(tmp_path):
    registry, devices, _ = config(tmp_path)
    payload = json.loads(devices.read_text(encoding="utf-8"))
    payload["devices"][0]["ramal"] = "t10-1001"
    devices.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="diverge"):
        pv.load_policy(registry, devices)


def test_vendedor_nao_homologado_e_negado(tmp_path):
    registry, devices, _ = config(tmp_path)
    payload = json.loads(devices.read_text(encoding="utf-8"))
    payload["devices"][0]["vendor"] = "fabricante-desconhecido"
    devices.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="diverge"):
        pv.load_policy(registry, devices)


def test_config_binaria_positiva_sem_lista_ou_outros_arquivos(tmp_path):
    _, _, folder = config(tmp_path)
    assert pv.read_cfg(folder, MAC1) == b"user=t1-1001\npassword=secret-t1"
    for value in ("../secrets", "AABBCCDDEEFF", MAC1 + ".cfg", "%2e%2e"):
        with pytest.raises(ValueError, match="MAC invalido"):
            pv.read_cfg(folder, value)


def test_symlink_para_segredo_externo_e_negado(tmp_path):
    _, _, folder = config(tmp_path)
    external = tmp_path / "private"
    external.write_text("TOP-SECRET")
    file = folder / (MAC1 + ".cfg")
    file.unlink()
    file.symlink_to(external)
    with pytest.raises(OSError):
        pv.read_cfg(folder, MAC1)
    assert external.read_text() == "TOP-SECRET"


def test_symlink_de_diretorio_e_negado(tmp_path):
    _, _, folder = config(tmp_path)
    alias = tmp_path / "alias"
    alias.symlink_to(folder, target_is_directory=True)
    with pytest.raises(ValueError, match="diretorio"):
        pv.read_cfg(alias, MAC1)


def test_rejeita_configuracao_maior_do_limite(tmp_path):
    _, _, folder = config(tmp_path)
    (folder / (MAC1 + ".cfg")).write_bytes(b"A" * (pv.MAX_CFG + 1))
    with pytest.raises(ValueError, match="invalida"):
        pv.read_cfg(folder, MAC1)


class FakeTLS:
    def __init__(self, cert):
        self.cert = cert
    def getpeercert(self, *, binary_form):
        assert binary_form
        return self.cert


def handler_request(path, cert, root, registry, devices):
    handler = pv.ProvisioningHandler.__new__(pv.ProvisioningHandler)
    handler.path = path
    handler.connection = FakeTLS(cert)
    handler.server = SimpleNamespace(registry_path=str(registry),
                                     devices_path=str(devices), config_dir=str(root))
    handler.calls = []
    handler._respond = lambda code, data=b"": handler.calls.append((code, data))
    handler.do_GET()
    return handler.calls


@pytest.mark.parametrize("path", [
    "/", "/aabbccddeeff.cfg/", "/../aabbccddeeff.cfg",
    "/aabbccddeeff.cfg?token=secret", "/%61abbccddeeff.cfg",
    "/001122334455.cfg/../aabbccddeeff.cfg", "/AABBCCDDEEFF.cfg",
])
def test_rejeita_travessia_listagem_url_com_query_e_maiuscula(tmp_path, path):
    registry, devices, folder = config(tmp_path)
    assert handler_request(path, CLIENT1, folder, registry, devices) == [(404, b"")]


def test_http_retorna_config_apenas_para_certificado_do_mac(tmp_path):
    registry, devices, folder = config(tmp_path)
    assert handler_request("/" + MAC1 + ".cfg", CLIENT1, folder, registry, devices) == [
        (200, b"user=t1-1001\npassword=secret-t1")]
    assert handler_request("/" + MAC1 + ".cfg", CLIENT2, folder, registry, devices) == [(404, b"")]
    assert handler_request("/" + MAC2 + ".cfg", CLIENT1, folder, registry, devices) == [(404, b"")]
    assert handler_request("/" + MAC1 + ".cfg", None, folder, registry, devices) == [(404, b"")]


def test_resposta_impede_cache_publico_e_never_logs():
    handler = pv.ProvisioningHandler.__new__(pv.ProvisioningHandler)
    handler.wfile = io.BytesIO()
    status, headers = [], []
    handler.send_response = lambda code: status.append(code)
    handler.send_header = lambda k, v: headers.append((k, v))
    handler.end_headers = lambda: None
    handler._respond(200, b"secret")
    assert status == [200]
    assert ("Cache-Control", "no-store, private, max-age=0") in headers
    assert ("Pragma", "no-cache") in headers
    assert ("X-Content-Type-Options", "nosniff") in headers
    assert handler.wfile.getvalue() == b"secret"
    assert handler.log_message("%s", "PRIVATE-PASSWORD") is None


@pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl nao instalado")
def test_tls_real_certificado_e_restricao_tenant_mac(tmp_path):
    """Handshake mTLS de verdade com CA local e dois certificados temporarios."""
    registry, devices, folder = config(tmp_path)
    def run(*args):
        subprocess.run(["openssl", *args], cwd=tmp_path, check=True,
                       capture_output=True, timeout=12)
    run("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
        "-keyout", "ca.key", "-out", "ca.crt", "-subj", "/CN=AXE-PV-CA")
    for name, cn, usage in (("server", "localhost", "serverAuth"),
                            ("client1", "tenant1", "clientAuth"),
                            ("client2", "tenant2", "clientAuth")):
        run("req", "-newkey", "rsa:2048", "-nodes", "-keyout", name + ".key",
            "-out", name + ".csr", "-subj", "/CN=" + cn)
        extra = (["-extfile", name + ".ext"])
        (tmp_path / (name + ".ext")).write_text(
            ("subjectAltName=IP:127.0.0.1\n" if name == "server" else "")
            + "extendedKeyUsage=" + usage + "\n", encoding="utf-8")
        run("x509", "-req", "-in", name + ".csr", "-CA", "ca.crt",
            "-CAkey", "ca.key", "-CAcreateserial", "-out", name + ".crt",
            "-days", "1", *extra)
    for n, mac, tenant in ((1, MAC1, "t1"), (2, MAC2, "t2")):
        payload = json.loads(registry.read_text(encoding="utf-8"))
        cert_pem = (tmp_path / ("client" + str(n) + ".crt")).read_text()
        der = ssl.PEM_cert_to_DER_cert(cert_pem)
        next(i for i in payload["devices"] if i["tenant"] == tenant)["client_sha256"] = hashlib.sha256(der).hexdigest()
        registry.write_text(json.dumps(payload), encoding="utf-8")
    policy = pv.load_policy(registry, devices)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_cert_chain(str(tmp_path / "server.crt"), str(tmp_path / "server.key"))
    context.load_verify_locations(cafile=str(tmp_path / "ca.crt"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), pv.ProvisioningHandler)
    server.daemon_threads = True
    server.registry_path = str(registry)
    server.devices_path = str(devices)
    server.config_dir = str(folder)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        def get(filename, name=None):
            ctx = ssl.create_default_context(cafile=str(tmp_path / "ca.crt"))
            if name:
                ctx.load_cert_chain(str(tmp_path / (name + ".crt")),
                                    str(tmp_path / (name + ".key")))
            with urllib.request.urlopen("https://127.0.0.1:" + str(port) + "/" + filename,
                                        context=ctx, timeout=4) as resp:
                return resp.read(), resp.headers
        body, headers = get(MAC1 + ".cfg", "client1")
        assert b"secret-t1" in body and b"secret-t2" not in body
        assert headers["Cache-Control"] == "no-store, private, max-age=0"
        with pytest.raises(urllib.error.HTTPError) as ex:
            get(MAC2 + ".cfg", "client1")
        assert ex.value.code == 404
        body, _ = get(MAC2 + ".cfg", "client2")
        assert b"secret-t2" in body
        with pytest.raises((urllib.error.URLError, ssl.SSLError, ConnectionError)):
            get(MAC1 + ".cfg", None)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
