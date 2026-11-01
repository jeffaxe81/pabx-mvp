"""REL-14: SIP INVITE real do Asterisk para dois troncos UDP somente loopback.

Os contatos dos gateways são sobrescritos APENAS no staging efêmero;
sem gateway ou operadora real. Um simulador SIP separado por tronco
confirma URI e responde 486 ao INVITE para liberar a chamada.
"""
from pathlib import Path
import re
import socket
import threading
import time

# Os destinos são sintéticos. Nenhuma chamada alcança serviços externos.
NATIONAL = "1198765432"
INTERNATIONAL = "004412345678"
SECONDARY_FINAL = "04412345678"
CASES = (
    ("t1-primary", "t1", "0" + NATIONAL, None, None, None, "primary", NATIONAL),
    ("t1-secondary", "t1", "0" + INTERNATIONAL, None, None, None, "secondary", SECONDARY_FINAL),
    ("t2-primary", "t2", "0" + NATIONAL, None, None, None, "primary", NATIONAL),
    ("t2-international", "t2", "0" + INTERNATIONAL, None, None, None, "primary", INTERNATIONAL),
    ("t1-international-deny", "t1", "0" + INTERNATIONAL, "t1", None, None, None, None),
    ("t2-international-deny", "t2", "0" + INTERNATIONAL, "t2", None, None, None, None),
    ("t1-primary-blocklist", "t1", "0" + NATIONAL, None, NATIONAL, None, None, None),
    ("t1-secondary-blocklist", "t1", "0" + INTERNATIONAL, None, None, SECONDARY_FINAL, None, None),
    ("t1-after-t2-deny", "t1", "0" + INTERNATIONAL, "t2", None, None, "secondary", SECONDARY_FINAL),
)


def required_trunk_checks():
    return {"trunks_bound_loopback", "trunks_runtime_contexts", "trunks_no_operator_network"} | {
        "trunk:" + case[0] for case in CASES
    }


def parse_invite_target(data, port):
    """Apenas URI do INVITE, sem revelar outros cabeçalhos."""
    try:
        line = data.split(b"\r\n", 1)[0].decode("ascii", errors="strict")
    except UnicodeError:
        return "invalid-uri"
    match = re.fullmatch(
        r"INVITE sip:([0-9]{3,15})@127\.0\.0\.1:" + str(port)
        + r"(?:;[a-zA-Z0-9_=-]+)* SIP/2\.0", line)
    return match.group(1) if match else "invalid-uri"


class LoopbackTrunk:
    def __init__(self, name):
        self.name = name
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(0.15)
        self.port = self.sock.getsockname()[1]
        self.events = []
        self._stop = threading.Event()
        self.worker = None

    def start(self):
        if self.worker is not None:
            raise RuntimeError("trunk SIP já iniciado")
        self.worker = threading.Thread(target=self._receive, daemon=True)
        self.worker.start()

    def _receive(self):
        while not self._stop.is_set():
            try:
                data, addr = self.sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            if addr[0] != "127.0.0.1" or not data.startswith(b"INVITE "):
                continue
            target = parse_invite_target(data, self.port)
            self.events.append(target)
            # 486 é resposta final negativa, não simula atendimento/áudio.
            # Encaminhar somente os cabeçalhos SIP necessários à transação.
            headers = {}
            for line in data.split(b"\r\n\r\n", 1)[0].split(b"\r\n")[1:]:
                if b":" in line:
                    key, value = line.split(b":", 1)
                    key = key.strip().lower()
                    if key in (b"via", b"from", b"to", b"call-id", b"cseq"):
                        headers.setdefault(key, []).append(value.strip())
            if not all(len(headers.get(k, [])) == 1 for k in
                       (b"via", b"from", b"to", b"call-id", b"cseq")):
                continue
            if not re.fullmatch(rb"[1-9][0-9]* INVITE", headers[b"cseq"][0]):
                continue
            to = headers[b"to"][0]
            if b";tag=" not in to:
                to += b";tag=axe-rel14"
            response = b"\r\n".join([
                b"SIP/2.0 486 Busy Here",
                b"Via: " + headers[b"via"][0],
                b"From: " + headers[b"from"][0],
                b"To: " + to,
                b"Call-ID: " + headers[b"call-id"][0],
                b"CSeq: " + headers[b"cseq"][0],
                b"Content-Length: 0",
                b"",
                b"",
            ])
            try:
                self.sock.sendto(response, addr)
            except OSError:
                break

    def close(self):
        self._stop.set()
        self.sock.close()
        if self.worker is not None:
            self.worker.join(timeout=2)


def prepare_trunks(prepared):
    """Garantir substituição exata dos dois AORs, nunca editar o checkout."""
    primary, secondary = LoopbackTrunk("primary"), LoopbackTrunk("secondary")
    prepared["rel14_trunks"] = {"primary": primary, "secondary": secondary}
    path = Path(prepared["conf"]) / "pjsip.conf"
    text = path.read_text(encoding="utf-8")
    for source, trunk in (
        ("contact=sip:192.168.1.200:5060", primary),
        ("contact=sip:192.168.1.201:5060", secondary),
    ):
        if text.count(source) != 1:
            raise RuntimeError("contato do tronco SIP não corresponde ao modelo")
        text = text.replace(source, f"contact=sip:127.0.0.1:{trunk.port}")
    if "contact=sip:192.168.1." in text:
        raise RuntimeError("contato externo do gateway no sandbox")
    path.write_text(text, encoding="utf-8")
    path.chmod(0o600)
    file = Path(prepared["conf"]) / "generated" / "rel14_sip_trunks.conf"
    lines = []
    for name, tenant, dialed, *_ in CASES:
        lines.extend((f"[lab-rel14-{name}]", "exten => s,1,Answer()",
                      f" same => n,Goto({tenant}-internal,{dialed},1)", ""))
    file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    file.chmod(0o600)
    ext = Path(prepared["conf"]) / "extensions.conf"
    ext.write_text(ext.read_text(encoding="utf-8")
                   + "\n#include generated/rel14_sip_trunks.conf\n", encoding="utf-8")
    ext.chmod(0o600)


def close_trunks(prepared):
    if prepared:
        for trunk in prepared.get("rel14_trunks", {}).values():
            trunk.close()


def exercise_trunks(container, prepared, report):
    from .asterisk_lab import cli
    checks = report["checks"]
    checks.update({key: False for key in required_trunk_checks()})
    sinks = prepared["rel14_trunks"]
    checks["trunks_bound_loopback"] = all(
        trunk.sock.getsockname()[0] == "127.0.0.1" for trunk in sinks.values()
    ) and sinks["primary"].port != sinks["secondary"].port
    checks["trunks_no_operator_network"] = checks["trunks_bound_loopback"]
    checks["trunks_runtime_contexts"] = all(
        "lab-rel14-" + name in cli(container, "dialplan show lab-rel14-" + name)
        for name, *_ in CASES
    )
    if not all(checks[x] for x in (
        "trunks_bound_loopback", "trunks_no_operator_network", "trunks_runtime_contexts"
    )):
        raise RuntimeError("preflight do tronco local não validado")
    for sink in sinks.values():
        sink.start()
    report["trunk_cases"] = {}
    for name, tenant, dialed, policy_block, original_block, normalized_block, gateway, number in CASES:
        report["phase"] = "trunk:" + name
        for t in ("t1", "t2"):
            cli(container, f"database del politica-externa-{t} internacional")
        cli(container, f"database del blocklist-{tenant} {NATIONAL}")
        cli(container, f"database del blocklist-{tenant} {INTERNATIONAL}")
        cli(container, f"database del blocklist-{tenant} {SECONDARY_FINAL}")
        if policy_block:
            cli(container, f"database put politica-externa-{policy_block} internacional bloquear")
        if original_block:
            cli(container, f"database put blocklist-{tenant} {original_block} 1")
        if normalized_block:
            cli(container, f"database put blocklist-{tenant} {normalized_block} 1")
        offsets = {key: len(sink.events) for key, sink in sinks.items()}
        cli(container, f"channel originate Local/s@lab-rel14-{name} application Wait 1")
        deadline = time.monotonic() + (2.5 if gateway else 0.8)
        observed = {}
        while time.monotonic() < deadline:
            observed = {key: sink.events[offsets[key]:] for key, sink in sinks.items()}
            if gateway and observed[gateway]:
                break
            time.sleep(0.05)
        # Detectar INVITE em outro gateway que chegue com pequeno atraso.
        time.sleep(0.20)
        observed = {key: sink.events[offsets[key]:] for key, sink in sinks.items()}
        expected = {key: ([number] if key == gateway else []) for key in sinks}
        passed = observed == expected
        checks["trunk:" + name] = passed
        report["trunk_cases"][name] = {
            "tenant": tenant, "passed": passed, "expected_gateway": gateway,
            "observed_gateways": {key: len(v) for key, v in observed.items()},
            "request_uri_verified": passed if gateway else None,
            "policy_or_blocklist_rejection": passed if gateway is None else None,
        }
        if not passed:
            # Expor apenas os dígitos artificiais dos casos de teste.
            print("REL14_MISMATCH", name, "expected", expected, "observed", observed, flush=True)
            raise RuntimeError("roteamento SIP de tronco divergente")
    report["sip_loopback_gateway_routing_tested"] = all(
        checks[key] for key in required_trunk_checks())
    report["real_operator_gateway_tested"] = False
