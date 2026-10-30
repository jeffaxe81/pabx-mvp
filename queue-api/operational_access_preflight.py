#!/usr/bin/env python3
"""Pré-voo LOCAL de 20 controles de identidade e gravações AXE PABX.

Lê catálogos privados do ambiente de execução, sem tokens em claro.
Não consulta serviços, não modifica dados e NUNCA autoriza produção.
"""
import argparse
import json
import math
import os
import stat
import sys
import time

from queue_access import authenticate_queue, load_queue_policy, may_pickup
from recording_access import (
    authenticate_recordings, can_read_recording, load_recording_policy,
)
from monitoring_access import extension_tenant

MAX_FUTURE_SECONDS = 86400
NEAR_EXPIRY_SECONDS = 300

CHECKS = (
    ("AC-01", "queue", "Arquivo de credenciais de fila privado (sem outros acessos)"),
    ("AC-02", "queue", "Catálogo de filas válido com abertura segura"),
    ("AC-03", "queue", "Catálogo de filas não vazio"),
    ("AC-04", "queue", "Ao menos uma credencial ativa de fila"),
    ("AC-05", "queue", "Supervisão com credencial ativa supervisor/admin"),
    ("AC-06", "queue", "Sem credenciais de fila expiradas retidas"),
    ("AC-07", "queue", "Sem credencial com mais de 24h de validade restante"),
    ("AC-08", "queue", "Sem credencial ativa a expirar nos próximos 5 minutos"),
    ("AC-09", "queue", "Pickup sintético de outro tenant é recusado"),
    ("AC-10", "queue", "Requisição Bearer ausente é recusada"),
    ("RC-01", "recording", "Arquivo de ACL de gravações privado"),
    ("RC-02", "recording", "Catálogo de gravações válido com abertura segura"),
    ("RC-03", "recording", "Credencial ativa de acesso às gravações"),
    ("RC-04", "recording", "Sem credenciais de gravação expiradas retidas"),
    ("RC-05", "recording", "Sem credencial com mais de 24h de validade restante"),
    ("RC-06", "recording", "Catálogo contém ao menos uma gravação classificada"),
    ("RC-07", "recording", "Todas gravações classificadas têm referência de origem"),
    ("RC-08", "recording", "Proprietários de gravações vinculados ao tenant correto"),
    ("RC-09", "recording", "Acesso sintético de outro tenant à gravação é negado"),
    ("RC-10", "recording", "Agente sem propriedade não acessa gravação"),
)


def _private_file(path):
    """lstat não segue link final; o loader valida também os ancestrais."""
    try:
        info = os.lstat(path)
    except (OSError, TypeError, ValueError):
        return False
    return stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) & 0o077 == 0


def _status(ok):
    return "unknown" if ok is None else ("pass" if ok else "fail")


def _safe_validity(credentials, now):
    """Separa status técnico e limpeza de tokens vencidos."""
    active = [row for row in credentials if row["expires_at"] > now]
    return {
        "present": bool(credentials),
        "active": bool(active),
        "no_expired": len(active) == len(credentials),
        "no_overlong_remaining": all(row["expires_at"] <= now + MAX_FUTURE_SECONDS
                                     for row in active),
        "not_near_expiry": (all(row["expires_at"] - now > NEAR_EXPIRY_SECONDS
                                for row in active) if active else None),
        "active_supervisor": any(row["role"] in ("supervisor", "admin") for row in active),
    }


def run_preflight(queue_path, recording_path, *, now=None):
    """Executa 20 checks com estado PASS/FAIL/UNKNOWN, sem PII.

    Checks que dependem de catálogos inválidos são UNKNOWN, e não PASS.
    Quadro de controles é diagnóstico local, não atesta chamada ou ACL HTTP.
    """
    current = time.time() if now is None else now
    if type(current) not in (int, float) or not math.isfinite(current) or current < 0:
        raise ValueError("relógio inválido")
    private_q = _private_file(queue_path)
    private_r = _private_file(recording_path)
    q = load_queue_policy(queue_path) if private_q else None
    r = load_recording_policy(recording_path) if private_r else None
    qvalid = isinstance(q, dict)
    rvalid = isinstance(r, dict)
    qcreds = q["credentials"] if qvalid else []
    rcreds = r["credentials"] if rvalid else []
    qstats = _safe_validity(qcreds, current) if qvalid else None
    rstats = _safe_validity(rcreds, current) if rvalid else None
    known = lambda stats, key: stats[key] if stats is not None else None

    # Autorização em memória: a CLI não envia qualquer chamada HTTP/AMI.
    # Os controles sintéticos só rodam se o catálogo correspondente é válido.
    deny_other_pickup = (not may_pickup(
        {"tenant": "t1", "role": "supervisor"}, "t10-recepcao"
    )) if qvalid else None
    deny_anonymous_queue = (
        authenticate_queue(None, q, now=current) is None
    ) if qvalid else None

    catalog = r["recordings"] if rvalid else None
    recordings = list(catalog.items()) if catalog is not None else []
    all_provenance = (all(isinstance(metadata.get("source_ref"), str)
                          and bool(metadata["source_ref"])
                          for _, metadata in recordings) if recordings else None)
    all_owner_scoped = (all(
        metadata.get("owner_extension") is None or
        extension_tenant(metadata["owner_extension"]) == metadata["tenant"]
        for _, metadata in recordings
    ) if recordings else None)
    other_tenant_denied = None
    non_owner_denied = None
    if recordings:
        filename, metadata = recordings[0]
        tenant = metadata["tenant"]
        foreign = "t1" if tenant != "t1" else "t10"
        other_tenant_denied = not can_read_recording(
            r, {"tenant": foreign, "role": "admin"}, filename
        )
        non_owner_denied = not can_read_recording(
            r, {"tenant": tenant, "role": "agent",
                "extension": tenant + "-non-owner"}, filename
        )

    decisions = (
        private_q,
        qvalid if private_q else None,
        known(qstats, "present"),
        known(qstats, "active"),
        known(qstats, "active_supervisor"),
        known(qstats, "no_expired"),
        known(qstats, "no_overlong_remaining"),
        known(qstats, "not_near_expiry"),
        deny_other_pickup,
        deny_anonymous_queue,
        private_r,
        rvalid if private_r else None,
        known(rstats, "active"),
        known(rstats, "no_expired"),
        known(rstats, "no_overlong_remaining"),
        bool(recordings) if rvalid else None,
        all_provenance,
        all_owner_scoped,
        other_tenant_denied,
        non_owner_denied,
    )
    if len(decisions) != len(CHECKS):
        raise ValueError("controles incompletos")
    rows = [
        {"id": cid, "domain": domain, "control": title, "status": _status(decision)}
        for (cid, domain, title), decision in zip(CHECKS, decisions)
    ]
    counts = {status: sum(row["status"] == status for row in rows)
              for status in ("pass", "fail", "unknown")}
    return {
        "schema_version": 1, "kind": "local_access_preflight",
        "checks_total": len(rows), "counts": counts, "checks": rows,
        "local_policy_files_read_only": True,
        "synthetic_authorization_checks_not_http": True,
        "token_values_or_hashes_exposed": False,
        "call_or_recording_media_proof_executed": False,
        "operational_homologation_claimed": False,
        "operational_go_authorized": False,
        "security_review_ready": counts["pass"] == 20,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-policy", required=True)
    parser.add_argument("--recordings-policy", required=True)
    args = parser.parse_args(argv)
    try:
        result = run_preflight(args.queue_policy, args.recordings_policy)
    except (OSError, ValueError, TypeError):
        print("Pré-voo inválido ou indisponível.", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["security_review_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
