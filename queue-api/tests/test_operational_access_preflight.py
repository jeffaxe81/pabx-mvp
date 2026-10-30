"""Provas sintéticas do pré-voo de 20 controles; sem dados reais/AMI."""
import hashlib
import json

import pytest

from operational_access_preflight import CHECKS, main, run_preflight

NOW = 1700000000


def credential(tenant="t1", role="supervisor", expires=NOW + 3600, extension=None):
    obj = {
        "token_sha256": hashlib.sha256(
            (tenant + role + (extension or "")).encode("ascii")
        ).hexdigest(),
        "tenant": tenant, "role": role, "expires_at": expires,
    }
    if extension is not None:
        obj["extension"] = extension
    return obj


def valid_data():
    return (
        {"credentials": [
            credential("t1", "supervisor"),
            credential("t10", "agent", extension="t10-1001"),
        ]},
        {"credentials": [credential("t1", "supervisor")],
         "recordings": {
             "one.wav": {
                 "tenant": "t1", "source_ref": "CDR:1700000000.123",
                 "owner_extension": "t1-1001",
             },
             "two.wav": {
                 "tenant": "t10", "source_ref": "CDR:1700000001.123",
                 "owner_extension": "t10-1001",
             },
         }},
    )


def policies(tmp_path, q=None, r=None):
    default_q, default_r = valid_data()
    qp = tmp_path / "queue.json"
    rp = tmp_path / "recording.json"
    qp.write_text(json.dumps(default_q if q is None else q), encoding="utf-8")
    rp.write_text(json.dumps(default_r if r is None else r), encoding="utf-8")
    qp.chmod(0o600)
    rp.chmod(0o600)
    return qp, rp


def by_id(report):
    return {row["id"]: row["status"] for row in report["checks"]}


def test_twenty_real_policy_checks_pass_for_valid_private_catalogs(tmp_path):
    q, r = policies(tmp_path)
    report = run_preflight(q, r, now=NOW)
    assert len(CHECKS) == 20
    assert len({row[0] for row in CHECKS}) == 20
    assert report["checks_total"] == 20
    assert report["counts"] == {"pass": 20, "fail": 0, "unknown": 0}
    assert report["security_review_ready"] is True
    assert report["operational_go_authorized"] is False
    assert report["operational_homologation_claimed"] is False
    assert report["call_or_recording_media_proof_executed"] is False
    assert all("token_sha256" not in str(item) for item in report["checks"])
    assert "CDR:170000" not in json.dumps(report)
    assert "t10-1001" not in json.dumps(report)


def test_stale_tokens_and_weak_supervision_are_rejected(tmp_path):
    qdata, rdata = valid_data()
    qdata["credentials"][0]["expires_at"] = NOW - 1
    qdata["credentials"][1]["expires_at"] = NOW + 60
    rdata["credentials"][0]["expires_at"] = NOW - 1
    q, r = policies(tmp_path, qdata, rdata)
    s = by_id(run_preflight(q, r, now=NOW))
    assert s["AC-05"] == "fail"
    assert s["AC-06"] == "fail"
    assert s["AC-08"] == "fail"
    assert s["RC-03"] == "fail"
    assert s["RC-04"] == "fail"


def test_future_ttl_and_provenance_fail_without_automatic_cleanup(tmp_path):
    qdata, rdata = valid_data()
    qdata["credentials"][0]["expires_at"] = NOW + 86401
    rdata["credentials"][0]["expires_at"] = NOW + 86401
    rdata["recordings"]["one.wav"].pop("source_ref")
    q, r = policies(tmp_path, qdata, rdata)
    before = (q.read_bytes(), r.read_bytes())
    s = by_id(run_preflight(q, r, now=NOW))
    assert s["AC-07"] == "fail"
    assert s["RC-05"] == "fail"
    assert s["RC-07"] == "fail"
    assert (q.read_bytes(), r.read_bytes()) == before


def test_empty_recording_inventory_is_unknown_not_pass(tmp_path):
    qdata, rdata = valid_data()
    rdata["recordings"] = {}
    q, r = policies(tmp_path, qdata, rdata)
    s = by_id(run_preflight(q, r, now=NOW))
    assert s["RC-06"] == "fail"
    assert s["RC-07"] == "unknown"
    assert s["RC-08"] == "unknown"
    assert s["RC-09"] == "unknown"
    assert s["RC-10"] == "unknown"


def test_empty_queue_credentials_cannot_look_operationally_ready(tmp_path):
    qdata, rdata = valid_data()
    qdata["credentials"] = []
    q, r = policies(tmp_path, qdata, rdata)
    s = by_id(run_preflight(q, r, now=NOW))
    assert s["AC-03"] == "fail"
    assert s["AC-04"] == "fail"
    assert s["AC-05"] == "fail"
    assert s["AC-08"] == "unknown"


def test_insecure_permissions_symlink_and_invalid_catalogs_fail_closed(tmp_path):
    q, r = policies(tmp_path)
    q.chmod(0o644)
    s = by_id(run_preflight(q, r, now=NOW))
    assert s["AC-01"] == "fail"
    assert s["AC-02"] == "unknown"
    assert s["RC-01"] == "pass"
    q.chmod(0o600)
    r.write_text("{bad json", encoding="utf-8")
    s = by_id(run_preflight(q, r, now=NOW))
    assert s["RC-01"] == "pass"
    assert s["RC-02"] == "fail"
    assert s["RC-09"] == "unknown"
    r.unlink()
    r.symlink_to(q)
    s = by_id(run_preflight(q, r, now=NOW))
    assert s["RC-01"] == "fail"
    assert s["RC-02"] == "unknown"


@pytest.mark.parametrize("clock", [True, "now", -1, float("inf"), float("nan")])
def test_invalid_clock_does_not_certify_anything(tmp_path, clock):
    q, r = policies(tmp_path)
    with pytest.raises(ValueError):
        run_preflight(q, r, now=clock)


def test_cross_tenant_denial_even_with_t1_t10_and_no_owner(tmp_path):
    qdata, rdata = valid_data()
    rdata["recordings"]["one.wav"].pop("owner_extension")
    q, r = policies(tmp_path, qdata, rdata)
    s = by_id(run_preflight(q, r, now=NOW))
    assert s["AC-09"] == "pass"
    assert s["AC-10"] == "pass"
    assert s["RC-09"] == "pass"
    assert s["RC-10"] == "pass"


def test_cli_does_not_print_sensitive_paths_or_digests_on_error(tmp_path, capsys):
    q, r = policies(tmp_path)
    code = main(["--queue-policy", str(q), "--recordings-policy", str(r)])
    # The fixed synthetic timestamp is in the past; credentials are expired.
    assert code == 1
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report["checks_total"] == 20
    assert "token_sha256" not in output
    assert str(q) not in output and str(r) not in output


def test_nonexistent_private_paths_do_not_throw_and_never_go(tmp_path):
    report = run_preflight(tmp_path / "not-there", tmp_path / "missing", now=NOW)
    assert report["security_review_ready"] is False
    assert report["counts"]["fail"] == 2
    assert report["counts"]["unknown"] >= 2
