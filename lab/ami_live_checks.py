"""AMI real somente no Asterisk descartável: primeira prova de OriginateResponse.

Não marca DialEnd/campanhas/callbacks como homologados. Os canais Local
não telefonam para ninguém e todos os dados AMI ficam apenas na memória.
"""
import queue
import secrets
import sys
import time
from pathlib import Path


def _production_modules():
    # Importar a mesma implementação de AMI e correlação usada pela queue-api.
    path = str(Path(__file__).resolve().parents[1] / "queue-api")
    if path not in sys.path:
        sys.path.insert(0, path)
    from ami_client import AMIClient
    from outbound_correlation import channel_id_for, matches_originate_response
    return AMIClient, channel_id_for, matches_originate_response


def prepare_ami(prepared):
    """Habilitar AMI só no namespace/host descartável, exclusivamente loopback."""
    conf = prepared["conf"]
    secret = secrets.token_hex(32)
    manager = conf / "manager.conf"
    manager.write_text(
        "[general]\n"
        "enabled=yes\n"
        "port=5038\n"
        "bindaddr=127.0.0.1\n"
        "displayconnects=no\n"
        "\n[axe-lab]\n"
        "secret=" + secret + "\n"
        "read=system,call\n"
        "write=originate,call\n"
        "deny=0.0.0.0/0.0.0.0\n"
        "permit=127.0.0.1/255.255.255.255\n"
    )
    manager.chmod(0o600)
    extensions = conf / "extensions.conf"
    # Contexto isolado e não acessível pelos ramais normais.
    with extensions.open("a") as output:
        output.write(
            "\n; AXE AMI LAB (apenas preparação descartável)\n"
            "[axe-ami-lab]\n"
            "exten => start,1,NoOp(AXE AMI Lab dial probe)\n"
            " same => n,Dial(Local/target@axe-ami-lab/n,4)\n"
            " same => n,Hangup()\n"
            "exten => target,1,Answer()\n"
            " same => n,Wait(1)\n"
            " same => n,Hangup()\n"
            "exten => after,1,Answer()\n"
            " same => n,Wait(2)\n"
            " same => n,Hangup()\n"
        )
    prepared["ami_username"] = "axe-lab"
    prepared["ami_secret"] = secret


def assess_response(event, attempt_id, channel_id, tenant="t1"):
    """Avaliar evidência real sem publicar evento, telefone ou credencial."""
    _, channel_id_for, matches = _production_modules()
    record = {"attempt_id": attempt_id, "channel_id": channel_id, "tenant": tenant}
    valid = matches(event, record)
    return {
        "ami_event_observed": isinstance(event, dict) and event.get("Event") == "OriginateResponse",
        "ami_action_channel_correlated": valid,
        "ami_originate_success": valid and event.get("Response") == "Success",
        "ami_wrong_action_rejected": not matches(
            {**event, "ActionID": "0" * 32}, record) if isinstance(event, dict) else False,
        "ami_wrong_channel_rejected": not matches(
            {**event, "Uniqueid": "axe-" + "0" * 32}, record) if isinstance(event, dict) else False,
        "ami_channel_id_format": channel_id_for(attempt_id) == channel_id,
    }


def required_ami_checks():
    return {"ami_login", "ami_action_queued", "ami_event_observed",
            "ami_action_channel_correlated", "ami_originate_success",
            "ami_wrong_action_rejected", "ami_wrong_channel_rejected",
            "ami_channel_id_format"}


def assess_local_dial_trace(events, channel_id, tenant="t1"):
    """Sanitized, observational Local/ leg evidence; NOT campaign/callback GO.

    Only a real runtime producing the supplied events can establish their
    provenance. This parser does not assert delivery, media, CDR or a public
    trunk; phone numbers and raw AMI frames never leave the caller.
    """
    begins = [e for e in events if isinstance(e, dict)
              and e.get("Event") == "DialBegin"]
    ends = [e for e in events if isinstance(e, dict)
            and e.get("Event") == "DialEnd"]
    def trusted(e):
        return (e.get("AccountCode", e.get("Accountcode")) == tenant
                and isinstance(e.get("Uniqueid"), str)
                and isinstance(e.get("DestUniqueid"), str)
                and isinstance(e.get("Linkedid"), str)
                and all(e.get(k) for k in ("Uniqueid", "DestUniqueid", "Linkedid")))
    pairs = [(b, e) for b in begins for e in ends
             if trusted(b) and trusted(e)
             and all(b.get(k) == e.get(k)
                     for k in ("Uniqueid", "DestUniqueid", "Linkedid"))]
    origin = any(channel_id in (e.get("Uniqueid"), e.get("DestUniqueid"),
                                e.get("Linkedid")) for e in begins + ends)
    return {
        "dial_begin_observed": bool(begins),
        "dial_end_observed": bool(ends),
        "dial_pair_identity_consistent": bool(pairs),
        "origin_channel_in_dial_trace": origin,
        "dial_answer_observed": any(e.get("DialStatus") == "ANSWER"
                                    for _, e in pairs),
        "local_probe_only": True,
    }


def exercise_ami(prepared, report):
    """Real AMI + Local/ observation, without calling trunks or users."""
    AMIClient, channel_id_for, _ = _production_modules()
    checks = report["checks"]
    for check in required_ami_checks():
        checks[check] = False
    report["live_ami_originate_response_tested"] = False
    # A Local/ leg is not a real campaign/callback or verified two-leg PJSIP call.
    report["live_ami_dialend_correlated"] = False
    report["phase"] = "ami_local_dial_observation"
    attempt = secrets.token_hex(16)
    channel = channel_id_for(attempt)
    events = queue.Queue(maxsize=128)
    overflow = [False]

    def receive(event):
        if event.get("Event") in ("OriginateResponse", "DialBegin", "DialEnd"):
            try:
                events.put_nowait(event)
            except queue.Full:
                overflow[0] = True

    client = AMIClient("127.0.0.1", 5038, prepared["ami_username"],
                       prepared["ami_secret"], on_event=receive)
    try:
        client.connect_and_login(timeout=6)
        checks["ami_login"] = True
        response = client.send_action({
            "Action": "Originate",
            "Channel": "Local/start@axe-ami-lab/n",
            "Context": "axe-ami-lab",
            "Exten": "after",
            "Priority": "1",
            "Async": "true",
            "Timeout": "5000",
            "ActionID": attempt,
            "ChannelId": channel,
            "Account": "t1",
        })
        checks["ami_action_queued"] = (
            response.get("ActionID") == attempt and response.get("Response") == "Success"
        )
        deadline = time.monotonic() + 10
        matched, trace = [], []
        while time.monotonic() < deadline and not overflow[0]:
            try:
                event = events.get(timeout=min(0.5, max(0.01, deadline - time.monotonic())))
            except queue.Empty:
                continue
            if event.get("Event") == "OriginateResponse":
                if event.get("ActionID") == attempt:
                    matched.append(event)
            else:
                trace.append(event)
            if len(matched) > 1:
                break
            if matched and any(e.get("Event") == "DialBegin" for e in trace) and any(
                    e.get("Event") == "DialEnd" for e in trace):
                # Small bounded duplicate-event drain; do not publish frames.
                time.sleep(0.2)
                while not events.empty():
                    extra = events.get_nowait()
                    if extra.get("Event") == "OriginateResponse" and extra.get("ActionID") == attempt:
                        matched.append(extra)
                    elif extra.get("Event") in ("DialBegin", "DialEnd"):
                        trace.append(extra)
                break
        if len(matched) == 1 and not overflow[0]:
            checks.update(assess_response(matched[0], attempt, channel))
        else:
            report["ami_event_count_valid"] = False
        report["ami_local_dial_observation"] = assess_local_dial_trace(trace, channel)
        report["ami_local_dial_observation"]["events_within_limit"] = not overflow[0]
        report["live_ami_originate_response_tested"] = all(
            checks[name] for name in required_ami_checks())
    finally:
        client.stop()
