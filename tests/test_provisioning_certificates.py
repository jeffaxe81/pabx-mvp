"""Operacao local do cadastro real; nenhuma emissao ou chave privada."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from provisioning import mtls_server as pv

MAC1 = "aabbccddeeff"
MAC2 = "001122334455"
NOW = 1793700000
ROOT = Path(__file__).resolve().parents[1]


def setup_registry(tmp_path):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    registry = private / "certificates.json"
    devices = tmp_path / "devices.json"
    entries = [
        {"mac": MAC1, "tenant": "t1", "client_sha256": hashlib.sha256(b"client1").hexdigest(),
         "valid_from": NOW - 60, "valid_until": NOW + 3600, "revoked": False},
        {"mac": MAC2, "tenant": "t10", "client_sha256": hashlib.sha256(b"client10").hexdigest(),
         "valid_from": NOW - 60, "valid_until": NOW + 3600, "revoked": False},
    ]
    registry.write_text(json.dumps({"schema_version": 2, "devices": entries}), encoding="utf-8")
    registry.chmod(0o600)
    devices.write_text(json.dumps({"devices": [
        {"mac": MAC1, "ramal": "t1-1001", "vendor": "yealink", "password": "SIP-SECRET"},
        {"mac": MAC2, "ramal": "t10-1001", "vendor": "yealink"},
    ]}), encoding="utf-8")
    return registry, devices


def operations():
    from provisioning import certificates
    return certificates


def cli(registry, devices, *args):
    return subprocess.run(
        [sys.executable, "-m", "provisioning.certificates", "--registry", str(registry),
         "--devices", str(devices), *args], cwd=ROOT, text=True, capture_output=True, timeout=15)


@pytest.mark.parametrize("tenant,wanted", [(None, ["t1", "t10"]), ("t1", ["t1"]), ("t10", ["t10"]), ("t2", [])])
def test_inventory_filters_exact_tenant_and_never_returns_certificates(tmp_path, tenant, wanted):
    registry, devices = setup_registry(tmp_path)
    result = operations().list_certificates(registry, devices, tenant, now=NOW)
    assert [r["tenant"] for r in result] == wanted
    for row in result:
        assert set(row) == {"tenant", "mac", "valid_from", "valid_until", "status"}
        assert row["status"] == "active"
    assert "client_sha256" not in json.dumps(result)
    assert "SIP-SECRET" not in json.dumps(result)


@pytest.mark.parametrize("moment,revoked,want", [
    (NOW - 61, False, "pending"), (NOW - 60, False, "active"),
    (NOW + 3599, False, "active"), (NOW + 3600, False, "expired"),
    (NOW, True, "revoked"), (NOW + 3600, True, "revoked"),
])
def test_inventory_obeys_validity_boundaries(tmp_path, moment, revoked, want):
    registry, devices = setup_registry(tmp_path)
    data = json.loads(registry.read_text())
    data["devices"][0]["revoked"] = revoked
    registry.write_text(json.dumps(data))
    assert operations().list_certificates(registry, devices, "t1", now=moment)[0]["status"] == want


@pytest.mark.parametrize("bad", [True, 0, -1, "today", float("nan"), float("inf"), 10 ** 1000])
def test_invalid_clock_fails_closed(tmp_path, bad):
    registry, devices = setup_registry(tmp_path)
    with pytest.raises(ValueError):
        operations().list_certificates(registry, devices, now=bad)


def test_revocation_preserves_other_tenant_and_is_idempotent(tmp_path):
    registry, devices = setup_registry(tmp_path)
    before = json.loads(registry.read_text())
    result = operations().revoke_certificate(registry, devices, "t1", MAC1)
    assert result == {"tenant": "t1", "mac": MAC1, "revoked": True, "changed": True}
    after = json.loads(registry.read_text())
    assert after["devices"][0]["revoked"] is True
    assert after["devices"][1] == before["devices"][1]
    assert registry.stat().st_mode & 0o777 == 0o600
    assert not pv.authorized(pv.load_policy(registry, devices), MAC1, b"client1", now=NOW)
    assert pv.authorized(pv.load_policy(registry, devices), MAC2, b"client10", now=NOW)
    stamp = registry.stat().st_mtime_ns
    assert operations().revoke_certificate(registry, devices, "t1", MAC1)["changed"] is False
    assert registry.stat().st_mtime_ns == stamp


@pytest.mark.parametrize("tenant,mac", [("t10", MAC1), ("t1", MAC2), ("t1", "../x"), ("t1", MAC1.upper()), ("t1\n", MAC1), (True, MAC1)])
def test_wrong_tenant_mac_or_identifier_does_not_modify_registry(tmp_path, tenant, mac):
    registry, devices = setup_registry(tmp_path)
    before = registry.read_bytes()
    with pytest.raises(ValueError):
        operations().revoke_certificate(registry, devices, tenant, mac)
    assert registry.read_bytes() == before


def test_failed_atomic_replace_preserves_original_and_cleans_temp(tmp_path, monkeypatch):
    registry, devices = setup_registry(tmp_path)
    before = registry.read_bytes()
    ops = operations()
    def fail(*args, **kwargs):
        raise OSError("disk failure containing SECRET")
    monkeypatch.setattr(ops.os, "replace", fail)
    with pytest.raises(OSError):
        ops.revoke_certificate(registry, devices, "t1", MAC1)
    assert registry.read_bytes() == before
    assert set(p.name for p in registry.parent.iterdir()) == {registry.name, registry.name + ".lock"}


@pytest.mark.parametrize("target", ["registry", "directory", "lock"])
def test_symlink_is_rejected_without_modifying_target(tmp_path, target):
    registry, devices = setup_registry(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_bytes(registry.read_bytes())
    outside.chmod(0o600)
    before = outside.read_bytes()
    if target == "registry":
        registry.unlink()
        registry.symlink_to(outside)
    elif target == "directory":
        alias = tmp_path / "alias"
        alias.symlink_to(registry.parent, target_is_directory=True)
        registry = alias / registry.name
    else:
        (registry.parent / (registry.name + ".lock")).symlink_to(outside)
    with pytest.raises((ValueError, OSError)):
        operations().revoke_certificate(registry, devices, "t1", MAC1)
    assert outside.read_bytes() == before


@pytest.mark.parametrize("target,mode", [("registry", 0o644), ("directory", 0o755), ("lock", 0o644)])
def test_public_permissions_are_rejected(tmp_path, target, mode):
    registry, devices = setup_registry(tmp_path)
    lock = registry.parent / (registry.name + ".lock")
    lock.touch(mode=0o600)
    {"registry": registry, "directory": registry.parent, "lock": lock}[target].chmod(mode)
    before = registry.read_bytes()
    with pytest.raises(ValueError):
        operations().revoke_certificate(registry, devices, "t1", MAC1)
    assert registry.read_bytes() == before


def test_concurrent_processes_do_not_lose_revocations(tmp_path):
    registry, devices = setup_registry(tmp_path)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(cli, registry, devices, "revoke", "--tenant", t, "--mac", m)
                   for t, m in (("t1", MAC1), ("t10", MAC2))]
        results = [f.result() for f in futures]
    assert [r.returncode for r in results] == [0, 0], [r.stderr for r in results]
    assert all(row["revoked"] for row in json.loads(registry.read_text())["devices"])


def test_cli_lists_and_revokes_without_dumping_private_data(tmp_path):
    registry, devices = setup_registry(tmp_path)
    result = cli(registry, devices, "list", "--tenant", "t1")
    assert result.returncode == 0, result.stderr
    assert len(json.loads(result.stdout)["devices"]) == 1
    revoked = cli(registry, devices, "revoke", "--tenant", "t1", "--mac", MAC1)
    assert revoked.returncode == 0, revoked.stderr
    assert json.loads(revoked.stdout)["revoked"] is True
    for output in (result.stdout, result.stderr, revoked.stdout, revoked.stderr):
        assert "SIP-SECRET" not in output
        assert hashlib.sha256(b"client1").hexdigest() not in output


def test_cli_error_never_echoes_registry_content_or_path(tmp_path):
    registry, devices = setup_registry(tmp_path)
    registry.write_text("SECRET-MALFORMED-REGISTRY")
    result = cli(registry, devices, "revoke", "--tenant", "t1", "--mac", MAC1)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "SECRET" not in result.stderr
    assert str(registry) not in result.stderr
    assert "Traceback" not in result.stderr


def test_revokes_supported_5000_device_registry_without_serialization_growth(tmp_path):
    registry, devices = setup_registry(tmp_path)
    bindings, manifest = [], []
    for number in range(1, 5001):
        mac = f"{number:012x}"
        bindings.append({"mac": mac, "tenant": "t1", "client_sha256": f"{number:064x}",
                         "valid_from": NOW - 60, "valid_until": NOW + 3600, "revoked": False})
        manifest.append({"mac": mac, "vendor": "yealink", "ramal": "t1-1001"})
    registry.write_text(json.dumps({"schema_version": 2, "devices": bindings}, separators=(",", ":")))
    devices.write_text(json.dumps({"devices": manifest}, separators=(",", ":")))
    assert registry.stat().st_size < 1048576
    assert len(pv.load_policy(registry, devices)) == 5000
    result = operations().revoke_certificate(registry, devices, "t1", "000000000001")
    assert result["changed"] is True
    saved = json.loads(registry.read_text())
    assert saved["devices"][0]["revoked"] is True
    assert all(not entry["revoked"] for entry in saved["devices"][1:])
    assert len(pv.load_policy(registry, devices)) == 5000


def test_cli_deeply_nested_json_is_sanitized_and_returns_two(tmp_path):
    registry, devices = setup_registry(tmp_path)
    registry.write_text('{"devices":' + '[' * 20000 + '0' + ']' * 20000 + '}')
    result = cli(registry, devices, "list")
    assert result.returncode == 2
    assert result.stdout == ""
    assert "Traceback" not in result.stderr
    assert str(registry) not in result.stderr
