"""Prova HTTP com os WAVs produzidos pelo MixMonitor REAL no laboratório.

Executa a Handler real da queue-api em loopback, com CDR conferido,
tokens efêmeros e arquivos do container Asterisk descartável.
Nenhum WAV, segredo, nome opaco de arquivo ou cabeçalho é publicado na CI.
"""
import hashlib
import http.client
import importlib
import json
import os
from pathlib import Path
import secrets
import stat
import sys
import threading
import time
from http.server import ThreadingHTTPServer

from .recording_checks import TENANTS, MIN_AUDIO_BYTES, recording_cdr_reference

TEST_TENANTS = TENANTS + ("t10",)
ORIGIN = "https://private-axe-lab.invalid"
METRICS = ("rec_http_list", "rec_http_bytes", "rec_http_cross_denied",
           "rec_http_origin_denied")


def required_recording_http_checks():
    return ({f"{metric}:{tenant}" for tenant in TENANTS for metric in METRICS}
            | {"rec_http_unauthenticated", "rec_http_prefix_t10_denied",
               "rec_http_revoked_t1", "rec_http_other_tenants_unaffected",
               "rec_http_verified_cdr_sources"})


def _credential(token, tenant):
    return {
        "token_sha256": hashlib.sha256(token.encode("ascii")).hexdigest(),
        "tenant": tenant, "role": "supervisor", "expires_at": time.time() + 600,
    }


def _request(port, path, token=None, *, origin=None):
    headers = {}
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    if origin is not None:
        headers["Origin"] = origin
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=8)
    try:
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        # WAVs do laboratório são limitados antes da requisição; uma
        # resposta inesperada não pode consumir memória indefinidamente.
        payload = response.read(2 * 1024 * 1024 + 1)
        return response.status, dict(response.getheaders()), payload
    finally:
        connection.close()


def _read_lab_wav(path):
    """Apenas arquivo regular privado WAV sem links ou payload gigante."""
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or not MIN_AUDIO_BYTES <= info.st_size <= 2 * 1024 * 1024:
        raise ValueError("arquivo real de gravação inválido no laboratório")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError("gravação do laboratório com permissão pública")
    data = path.read_bytes()
    if len(data) != info.st_size or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("MixMonitor não produziu WAV íntegro")
    return data


def _write_private_policy(path, policy, *, create=False):
    data = (json.dumps(policy, sort_keys=True) + "\n").encode("utf-8")
    if create:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as opened:
            opened.write(data)
    else:
        # O arquivo é exclusivamente do laboratório, não compartilhado.
        if path.is_symlink():
            raise ValueError("política simbólica de teste")
        path.write_bytes(data)


def exercise_recording_http(container, prepared, report, raw_cdr):
    """Verifica download real e revogação; retorna apenas checks sanitizados."""
    from .asterisk_lab import command

    checks = report["checks"]
    checks.update({key: False for key in required_recording_http_checks()})
    report["real_recording_http_lab_tested"] = False
    report["recording_http_cases"] = {}
    names = prepared.get("lab_recording_filenames")
    if not isinstance(names, dict) or set(names) != set(TENANTS):
        raise ValueError("WAVs do laboratório não preparados")
    if len(set(names.values())) != len(TENANTS):
        raise ValueError("nomes de gravações não exclusivos")
    references = {tenant: recording_cdr_reference(raw_cdr, tenant)
                  for tenant in TENANTS}
    checks["rec_http_verified_cdr_sources"] = (
        all(isinstance(ref, str) and ref.startswith("CDR:") for ref in references.values())
        and len(set(references.values())) == len(TENANTS)
    )
    if not checks["rec_http_verified_cdr_sources"]:
        raise ValueError("CDR não demonstra origem exclusiva para os WAVs")

    # O diretório é privado e se encontra sob o staging que o runner apaga.
    directory = Path(prepared["conf"]).parent / "http-recording-lab"
    directory.mkdir(mode=0o700, exist_ok=False)
    original_audio = {}
    for tenant in TENANTS:
        name = names[tenant]
        if not isinstance(name, str) or not (
            len(name) == 28 and name.endswith(".wav")
            and all(char in "0123456789abcdef" for char in name[:-4])
        ):
            raise ValueError("nome efêmero de WAV inválido")
        source = f"/var/spool/asterisk/monitor/{tenant}/{name}"
        target = directory / name
        command(["docker", "cp", container + ":" + source, str(target)], timeout=20)
        target.chmod(0o600)
        original_audio[tenant] = _read_lab_wav(target)

    tokens = {tenant: secrets.token_urlsafe(40) for tenant in TEST_TENANTS}
    policy = {
        "credentials": [_credential(tokens[tenant], tenant) for tenant in TEST_TENANTS],
        "recordings": {
            names[tenant]: {
                "tenant": tenant, "owner_extension": tenant + "-1001",
                "source_ref": references[tenant],
            } for tenant in TENANTS
        },
    }
    policy_path = directory / "catalog.json"
    _write_private_policy(policy_path, policy, create=True)

    queue_api = str(Path(__file__).resolve().parents[1] / "queue-api")
    sys.path.insert(0, queue_api)
    try:
        server = importlib.import_module("server")
    finally:
        sys.path.remove(queue_api)

    class QuietHandler(server.Handler):
        def log_message(self, *_args):
            pass  # nenhuma URL com nome de arquivo vai ao log do runner

    settings = ("RECORDINGS_DIR", "RECORDINGS_ACCESS_POLICY_PATH",
                "RECORDINGS_CORS_ORIGINS")
    before = {key: getattr(server, key) for key in settings}
    host = None
    runner = None
    try:
        server.RECORDINGS_DIR = str(directory)
        server.RECORDINGS_ACCESS_POLICY_PATH = str(policy_path)
        server.RECORDINGS_CORS_ORIGINS = {ORIGIN}
        host = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        runner = threading.Thread(target=host.serve_forever, daemon=True)
        runner.start()
        port = host.server_address[1]
        for tenant in TENANTS:
            own_name = names[tenant]
            others = [names[other] for other in TENANTS if other != tenant]
            status, headers, payload = _request(
                port, "/api/recordings?tenant=t10", tokens[tenant], origin=ORIGIN
            )
            try:
                rows = json.loads(payload)["recordings"]
                listing = {row["filename"] for row in rows}
            except (ValueError, TypeError, KeyError):
                listing = set()
            checks["rec_http_list:" + tenant] = (
                status == 200 and listing == {own_name}
                and headers.get("Cache-Control") == "no-store"
            )
            status, headers, payload = _request(
                port, "/recordings/" + own_name, tokens[tenant], origin=ORIGIN
            )
            checks["rec_http_bytes:" + tenant] = (
                status == 200 and headers.get("Content-Type") == "audio/wav"
                and headers.get("Cache-Control") == "no-store"
                and payload == original_audio[tenant]
                and len(payload) >= MIN_AUDIO_BYTES
            )
            checks["rec_http_cross_denied:" + tenant] = all(
                (lambda response: response[0] == 404
                 and response[2] != original_audio[other]
                 and b"RIFF" not in response[2])(
                    _request(port, "/recordings/" + names[other], tokens[tenant])
                ) for other in TENANTS if other != tenant
            )
            status, headers, payload = _request(
                port, "/recordings/" + own_name, tokens[tenant],
                origin="https://untrusted.invalid",
            )
            checks["rec_http_origin_denied:" + tenant] = (
                status == 403 and b"RIFF" not in payload
                and "Access-Control-Allow-Origin" not in headers
            )
            report["recording_http_cases"][tenant] = {
                "own_list_only": checks["rec_http_list:" + tenant],
                "real_audio_exact": checks["rec_http_bytes:" + tenant],
                "foreign_audio_denied": checks["rec_http_cross_denied:" + tenant],
            }

        status, _, payload = _request(port, "/recordings/" + names["t1"])
        checks["rec_http_unauthenticated"] = status == 401 and b"RIFF" not in payload
        status, _, payload = _request(port, "/api/recordings?tenant=t1", tokens["t10"])
        listed = json.loads(payload).get("recordings") if status == 200 else None
        negatives = [
            _request(port, "/recordings/" + names[tenant], tokens["t10"])
            for tenant in TENANTS
        ]
        checks["rec_http_prefix_t10_denied"] = (
            status == 200 and listed == []
            and all(code == 404 and b"RIFF" not in body for code, _, body in negatives)
        )

        # Revogação precisa valer sem reiniciar a Handler de produção.
        policy["credentials"] = [
            row for row in policy["credentials"]
            if row["token_sha256"] != hashlib.sha256(tokens["t1"].encode()).hexdigest()
        ]
        _write_private_policy(policy_path, policy)
        denied_status, _, denied_body = _request(
            port, "/recordings/" + names["t1"], tokens["t1"]
        )
        checks["rec_http_revoked_t1"] = (
            denied_status == 401 and b"RIFF" not in denied_body
        )
        checks["rec_http_other_tenants_unaffected"] = all(
            (lambda response: response[0] == 200 and response[2] == original_audio[tenant])(
                _request(port, "/recordings/" + names[tenant], tokens[tenant])
            ) for tenant in ("t2", "t3")
        )
    finally:
        if host is not None:
            host.shutdown()
            host.server_close()
        if runner is not None:
            runner.join(timeout=5)
        for key, old in before.items():
            setattr(server, key, old)
    report["real_recording_http_lab_tested"] = all(
        checks[key] is True for key in required_recording_http_checks()
    )
