"""AMI AgentConnect gerado por Queue REAL, com mídia SIP/TLS-SRTP e SLA HTTP.

Somente no Asterisk descartável: um atendente SIP efêmero tN-1002 é
adicionado à fila original. Nunca substitui Queue() ou liga em operadora.
O relatório contém somente booleanos; não registra AMI bruto nem segredos.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from http.server import ThreadingHTTPServer
import hashlib
import http.client
import importlib
import json
from pathlib import Path
import queue
import re
import secrets
import sys
import threading
import time

from .sip_calls import CallPeer
from .srtp_media import SrtpMedia, exchange

TENANTS = ("t1", "t2", "t3")
PER_TENANT = (
    "registered", "queue_loaded", "answered_by_member", "srtp",
    "agentconnect_real", "cdr_same_call", "sla_count", "http_scoped",
    "bye", "channels_cleared",
)
GLOBAL = ("sla_ami_login", "sla_unauthorized_denied",
          "sla_t10_prefix_denied", "sla_cross_tenant_denied",
          "sla_no_event_overflow")


def required_live_queue_sla_checks():
    return ({f"sla_live_{name}:{tenant}" for name in PER_TENANT
             for tenant in TENANTS}
            | set(GLOBAL))


def _add_private_queue_member(path, tenant):
    text = Path(path).read_text(encoding="utf-8")
    section = f"[fila-{tenant}]\n"
    if text.count(section) != 1:
        raise ValueError("fila padrão não é exclusiva no staging")
    before, remainder = text.split(section, 1)
    own, separator, rest = remainder.partition("\n[")
    member = f"member => PJSIP/{tenant}-1002"
    if (member in own or "monitor-type = mixmonitor" not in own
            or "strategy = rrmemory" not in own):
        raise ValueError("fila real alterada ou membro já duplicado")
    staged = before + section + own.rstrip("\n") + "\n" + member + "\n"
    if separator:
        staged += "\n[" + rest
    Path(path).write_text(staged, encoding="utf-8")
    Path(path).chmod(0o600)


def prepare_live_queue_sla(prepared):
    """Acrescenta SOMENTE membros SIP testáveis à cópia das filas."""
    root = Path(prepared["conf"])
    for tenant in TENANTS:
        path = (root / "queues.conf" if tenant != "t3"
                else root / "queues_tenants" / "t3.conf")
        _add_private_queue_member(path, tenant)
    # Reusa a ACL do AMI de membros (loopback e usuário efêmero), sem
    # combinar este ensaio com --members ou --ami.
    from .queue_member_checks import prepare_members
    prepare_members(prepared)
    prepared["live_queue_sla_staged"] = True


def fresh_queue_cdr(raw, previous, tenant, uniqueid):
    """Um CDR novo da Queue com identidade exata e canal do atendente."""
    from .call_checks import cdr_rows
    rows = cdr_rows(raw)
    if (rows is None or not isinstance(previous, set)
            or tenant not in TENANTS
            or not isinstance(uniqueid, str)
            or re.fullmatch(r"[0-9]+\.[0-9]+", uniqueid) is None):
        return False
    matching = [
        row for row in rows if (
            row[8] == uniqueid and row[8] not in previous
            and row[0] == tenant and row[1] == "1001"
            and row[2] == "1000" and row[3] == tenant + "-internal"
            and re.fullmatch(r"PJSIP/" + tenant + r"-1001-[0-9a-f]+", row[4])
            and re.fullmatch(r"PJSIP/" + tenant + r"-1002-[0-9a-f]+", row[5])
            and row[6] == "ANSWERED" and row[7].isdigit()
            and int(row[7]) >= 1
        )
    ]
    return len(matching) == 1 and sum(row[8] == uniqueid for row in rows) == 1


def _http_json(port, path, token=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {} if token is None else {"Authorization": "Bearer " + token}
    try:
        conn.request("GET", path, headers=headers)
        result = conn.getresponse()
        raw = result.read(32769)
        if len(raw) > 32768:
            raise ValueError("resposta HTTP SLA excedeu limite")
        return result.status, json.loads(raw)
    finally:
        conn.close()


def check_sla_http(prepared, tracker, report):
    """Handler REAL + token temporário; filtro t1/t2/t3 e prefixo t10."""
    from .recording_http_checks import _write_private_policy
    checks = report["checks"]
    directory = Path(prepared["conf"]).parent / "queue-sla-http-lab"
    directory.mkdir(mode=0o700, exist_ok=False)
    tokens = {t: secrets.token_urlsafe(36) for t in (*TENANTS, "t10")}
    policy = {
        "credentials": [
            {
                "token_sha256": hashlib.sha256(tokens[t].encode()).hexdigest(),
                "tenant": t, "role": "supervisor",
                "expires_at": time.time() + 600,
            } for t in tokens
        ]
    }
    path = directory / "queue-credentials.json"
    _write_private_policy(path, policy, create=True)
    source = str(Path(__file__).resolve().parents[1] / "queue-api")
    if source not in sys.path:
        sys.path.insert(0, source)
    server = importlib.import_module("server")

    class QuietHandler(server.Handler):
        def log_message(self, *_args):
            pass

    original = (server.QUEUE_ACCESS_POLICY_PATH, server.queue_sla_tracker,
                server.SLA_THRESHOLD_SECONDS)
    host = None
    worker = None
    try:
        server.QUEUE_ACCESS_POLICY_PATH = str(path)
        server.queue_sla_tracker = tracker
        server.SLA_THRESHOLD_SECONDS = tracker.threshold_seconds
        host = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        worker = threading.Thread(target=host.serve_forever, daemon=True)
        worker.start()
        port = host.server_address[1]
        for tenant in TENANTS:
            status, response = _http_json(port, "/api/metrics/sla", tokens[tenant])
            checks[f"sla_live_http_scoped:{tenant}"] = (
                status == 200
                and set(response) == {"threshold_seconds", "queues"}
                and set(response["queues"]) == {"fila-" + tenant}
                and response["queues"]["fila-" + tenant] == {
                    "offered": 1, "within_sla": 1, "sla_percent": 100.0
                }
            )
        status, _ = _http_json(port, "/api/metrics/sla")
        checks["sla_unauthorized_denied"] = status == 401
        status, response = _http_json(port, "/api/metrics/sla", tokens["t10"])
        checks["sla_t10_prefix_denied"] = status == 200 and response["queues"] == {}
        checks["sla_cross_tenant_denied"] = all(
            _http_json(port, "/api/metrics/sla?tenant=" + other, tokens[tenant])[1]["queues"]
            == {"fila-" + tenant: {
                "offered": 1, "within_sla": 1, "sla_percent": 100.0
            }}
            for tenant in TENANTS for other in TENANTS if other != tenant
        )
    finally:
        if host is not None:
            host.shutdown()
            host.server_close()
        if worker is not None:
            worker.join(timeout=5)
        (server.QUEUE_ACCESS_POLICY_PATH,
         server.queue_sla_tracker,
         server.SLA_THRESHOLD_SECONDS) = original


def exercise_live_queue_sla(container, prepared, report):
    from .asterisk_lab import cli, command
    from .call_checks import cdr_rows
    from .queue_member_checks import _production_modules
    _, _, _, _ = _production_modules()
    from ami_client import AMIClient
    from queue_sla import QueueSLATracker

    checks = report["checks"]
    checks.update({key: False for key in required_live_queue_sla_checks()})
    report["live_queue_sla_tested"] = False
    report["phase"] = "sla-real-queue"
    if prepared.get("live_queue_sla_staged") is not True:
        raise ValueError("membro de SLA não preparado")
    incoming = queue.Queue(maxsize=512)
    overflow = [False]
    tracker = QueueSLATracker(threshold_seconds=20)

    def receive(event):
        if event.get("Event") != "AgentConnect":
            return
        try:
            incoming.put_nowait(event)
        except queue.Full:
            overflow[0] = True

    client = AMIClient("127.0.0.1", 5038,
                       prepared["members_ami_username"],
                       prepared["members_ami_secret"], on_event=receive)
    try:
        client.connect_and_login(timeout=6)
        checks["sla_ami_login"] = True
        for tenant in TENANTS:
            report["phase"] = "sla-queue:" + tenant
            queue_name = "fila-" + tenant
            checks[f"sla_live_queue_loaded:{tenant}"] = (
                f"PJSIP/{tenant}-1002" in cli(container, "queue show " + queue_name)
                and "Queue(" in cli(container, "dialplan show 1000@" + tenant + "-internal")
            )
            if not checks[f"sla_live_queue_loaded:{tenant}"]:
                raise ValueError("membro temporário de fila não carregado")
            initial = command(["docker", "exec", container, "cat",
                               "/var/log/asterisk/cdr-custom/Lab.csv"], check=False)
            prior = cdr_rows(initial.stdout) if initial.returncode == 0 else None
            if prior is None:
                raise ValueError("snapshot CDR anterior inválido")
            prior_ids = {row[8] for row in prior}
            with ExitStack() as resources, ThreadPoolExecutor(max_workers=1) as executor:
                caller = CallPeer("127.0.0.1", 5061, prepared["ca"], tenant + "-1001",
                                  prepared["credentials"][tenant + "-1001"])
                callee = CallPeer("127.0.0.1", 5061, prepared["ca"], tenant + "-1002",
                                  prepared["credentials"][tenant + "-1002"])
                resources.callback(caller.close)
                resources.callback(callee.close)
                left, right = SrtpMedia(), SrtpMedia()
                resources.callback(left.close)
                resources.callback(right.close)
                checks[f"sla_live_registered:{tenant}"] = (
                    caller.register() == 200 and callee.register() == 200
                )
                if not checks[f"sla_live_registered:{tenant}"]:
                    raise ValueError("registro SIP da fila rejeitado")
                future = executor.submit(callee.answer, right)
                caller_dialog = caller.dial("1000", left)
                callee_dialog = future.result(timeout=14)
                checks[f"sla_live_answered_by_member:{tenant}"] = True
                media = exchange(left, right, duration=1.5)
                checks[f"sla_live_srtp:{tenant}"] = (
                    media["authenticated"] and media["payloads_match"]
                    and media["tamper_rejected"] and media["replay_rejected"]
                )
                bye = executor.submit(callee.await_hangup, callee_dialog)
                checks[f"sla_live_bye:{tenant}"] = (
                    caller.hangup(caller_dialog) == 200
                    and bye.result(timeout=12)
                )
                caller.register(expires=0)
                callee.register(expires=0)

            # Não sintetizar AgentConnect! A origem deve ser o fluxo
            # Asterisk AMI real, da ligação acabada.
            found = []
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                try:
                    event = incoming.get(timeout=0.2)
                except queue.Empty:
                    if found:
                        break
                    continue
                if event.get("Queue") == queue_name:
                    found.append(event)
            checks[f"sla_live_agentconnect_real:{tenant}"] = (
                len(found) == 1
                and isinstance(found[0].get("Uniqueid"), str)
                and found[0].get("HoldTime", "").isascii()
                and found[0].get("HoldTime", "").isdecimal()
                and 0 <= int(found[0]["HoldTime"]) <= 20
                and not overflow[0]
            )
            if not checks[f"sla_live_agentconnect_real:{tenant}"]:
                raise ValueError("AgentConnect real não correlacionado")
            event = found[0]
            tracker.apply_event(event)
            checks[f"sla_live_sla_count:{tenant}"] = tracker.snapshot().get(queue_name) == {
                "offered": 1, "within_sla": 1, "sla_percent": 100.0
            }
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                cdr = command(["docker", "exec", container, "cat",
                               "/var/log/asterisk/cdr-custom/Lab.csv"], check=False)
                checks[f"sla_live_cdr_same_call:{tenant}"] = (
                    cdr.returncode == 0 and fresh_queue_cdr(
                        cdr.stdout, prior_ids, tenant, event.get("Uniqueid"))
                )
                lines = cli(container, "core show channels concise")
                checks[f"sla_live_channels_cleared:{tenant}"] = not any(
                    line.startswith("PJSIP/") for line in lines.splitlines())
                if (checks[f"sla_live_cdr_same_call:{tenant}"]
                        and checks[f"sla_live_channels_cleared:{tenant}"]):
                    break
                time.sleep(0.2)
            report.setdefault("queue_sla_cases", {})[tenant] = {
                "real_agentconnect": checks[f"sla_live_agentconnect_real:{tenant}"],
                "cdr_correlated": checks[f"sla_live_cdr_same_call:{tenant}"],
                "srtp_authenticated": checks[f"sla_live_srtp:{tenant}"],
            }
        checks["sla_no_event_overflow"] = not overflow[0] and incoming.empty()
        check_sla_http(prepared, tracker, report)
        report["live_queue_sla_tested"] = all(
            checks[key] is True for key in required_live_queue_sla_checks()
        )
    finally:
        client.stop()
