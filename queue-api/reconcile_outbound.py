"""Manual-only quarantine of stale outbound claims, with durable audit.

This tool NEVER redials or resets a contact to pending. Run it only on
the node with access to the shared queue-api volume after verifying AMI
and CDR history. Files must not be edited outside outbound_lock.
"""
import argparse
import hashlib
import json
import math
import re
import time
from pathlib import Path

from outbound_safety import outbound_lock, atomic_write_json, audit_event


def _valid_tenant(tenant):
    from monitoring_access import extension_tenant
    return isinstance(tenant, str) and extension_tenant(tenant + "-recepcao") == tenant


def _safe_attempt_id(value):
    return value if isinstance(value, str) and re.fullmatch(r"[a-f0-9]{32}", value) else None


def _candidate_records(records, kind, tenant, now, min_age):
    for entity in records:
        if not isinstance(entity, dict) or entity.get("tenant") != tenant:
            continue
        if kind == "callbacks":
            items = [(entity, entity.get("caller_id_num"))]
        else:
            items = [(item, item.get("number")) for item in entity.get("contacts", [])
                     if isinstance(item, dict)]
        for item, number in items:
            age_ref = item.get("last_attempt_at")
            if (item.get("status") != "discando"
                    or type(age_ref) not in (int, float)
                    or not math.isfinite(age_ref) or age_ref > now
                    or now - age_ref < min_age):
                continue
            yield entity, item, number


def inspect_claims(path, kind, tenant, min_age=600, now=None):
    if kind not in {"campaigns", "callbacks"} or not _valid_tenant(tenant):
        raise ValueError("invalid kind or tenant")
    if min_age < 300:
        raise ValueError("minimum age must be at least 300 seconds")
    now = time.time() if now is None else now
    with outbound_lock(path):
        data = json.loads(Path(path).read_text()) if Path(path).exists() else []
        if not isinstance(data, list):
            raise ValueError("invalid outbound snapshot")
        return [{
            "id": entity["id"],
            "attempt_id": _safe_attempt_id(item.get("attempt_id")),
            "number_sha256": hashlib.sha256(str(number).encode()).hexdigest(),
            "age_seconds": int(now - item["last_attempt_at"]),
            "state": "discando",
        } for entity, item, number in _candidate_records(data, kind, tenant, now, min_age)]


def quarantine_claim(path, kind, tenant, item_id, evidence, operator,
                     number=None, min_age=600, now=None):
    """Move a stale claim to review without authorizing another attempt."""
    if kind not in {"campaigns", "callbacks"} or not _valid_tenant(tenant):
        raise ValueError("invalid kind or tenant")
    if min_age < 300:
        raise ValueError("minimum age must be at least 300 seconds")
    if (not isinstance(operator, str) or not 2 <= len(operator.strip()) <= 100
            or not isinstance(evidence, str) or not 10 <= len(evidence.strip()) <= 512
            or "\n" in evidence or "\r" in evidence):
        raise ValueError("operator and documented evidence are required")
    if not isinstance(item_id, str) or not item_id:
        raise ValueError("item ID is required")
    now = time.time() if now is None else now
    with outbound_lock(path):
        data = json.loads(Path(path).read_text()) if Path(path).exists() else []
        if not isinstance(data, list):
            raise ValueError("invalid outbound snapshot")
        matches = [
            (entity, item, dialed) for entity, item, dialed
            in _candidate_records(data, kind, tenant, now, min_age)
            if entity.get("id") == item_id and (kind == "callbacks" or dialed == number)
        ]
        if len(matches) != 1:
            raise ValueError("claim not found, insufficiently old or ambiguous")
        _, item, dialed = matches[0]
        entry = {
            "action": "quarantine", "phase": "requested",
            "kind": kind, "tenant": tenant, "id": item_id,
            "attempt_id": _safe_attempt_id(item.get("attempt_id")),
            "number_sha256": hashlib.sha256(str(dialed).encode()).hexdigest(),
            "actor": operator.strip(), "evidence": evidence.strip(),
            "timestamp": now,
        }
        # Write-ahead audit: if snapshot replacement fails, leave a
        # requested-only record for investigation, never silently requeue.
        audit_event(path, entry)
        item["status"] = "revisao_manual"
        item["reviewed_at"] = now
        item["review_actor"] = operator.strip()
        atomic_write_json(path, data)
        audit_event(path, {**entry, "phase": "committed"})
        return {"id": item_id, "tenant": tenant, "status": "revisao_manual"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Manual outbound-claim quarantine (never auto-redial)")
    parser.add_argument("--path", required=True, help="path to campaigns.json or callbacks.json on shared volume")
    parser.add_argument("--kind", choices=("campaigns", "callbacks"), required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--min-age", type=int, default=600, help="seconds; at least 300")
    parser.add_argument("--quarantine-id", help="explicit ID to move to revisao_manual")
    parser.add_argument("--number", help="campaign contact number (not needed for callbacks)")
    parser.add_argument("--actor", help="operator responsible for review")
    parser.add_argument("--evidence", help="documented CDR/AMI confirmation, 10..512 characters")
    args = parser.parse_args(argv)
    if args.quarantine_id:
        if not args.actor or not args.evidence:
            parser.error("--actor and --evidence required to quarantine")
        result = quarantine_claim(args.path, args.kind, args.tenant,
                                  args.quarantine_id, args.evidence, args.actor,
                                  number=args.number, min_age=args.min_age)
    else:
        result = inspect_claims(args.path, args.kind, args.tenant, min_age=args.min_age)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
