"""Regressões do catálogo ACL de gravações contra symlink/TOCTOU.

Executa somente arquivos temporários, sem telefonia ou gravações reais.
"""
import hashlib
import json
import os

import pytest

import recording_access as access


TOKEN = "A" * 48


def valid_policy(tenant="t1"):
    return {
        "credentials": [{
            "token_sha256": hashlib.sha256(TOKEN.encode()).hexdigest(),
            "tenant": tenant,
            "role": "supervisor",
            "expires_at": 4102444800,
        }],
        "recordings": {"sample.wav": {"tenant": tenant}},
    }


def write_policy(path, tenant="t1"):
    payload = valid_policy(tenant)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def test_policy_read_valid_file(tmp_path):
    path = tmp_path / "catalog.json"
    expected = write_policy(path)
    assert access.load_recording_policy(path) == expected


def test_symlink_is_rejected_even_when_target_is_valid(tmp_path):
    original = tmp_path / "good.json"
    write_policy(original)
    symlink = tmp_path / "link.json"
    symlink.symlink_to(original)
    assert access.load_recording_policy(symlink) is None


def test_reject_fifo_without_blocking(tmp_path):
    if not hasattr(os, "mkfifo"):
        pytest.skip("FIFO is POSIX-only")
    fifo = tmp_path / "catalog.fifo"
    os.mkfifo(fifo)
    assert access.load_recording_policy(fifo) is None


def test_reject_oversize_file(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_bytes(b" " * (access.MAX_POLICY_BYTES + 1))
    assert access.load_recording_policy(path) is None


@pytest.mark.parametrize("original_valid", [True, False])
def test_swapping_path_after_open_does_not_change_opened_contents(
    monkeypatch, tmp_path, original_valid,
):
    path = tmp_path / "catalog.json"
    backup = tmp_path / "opened-original.json"
    attacker = tmp_path / "attacker.json"
    write_policy(path) if original_valid else path.write_text("{invalid-json", encoding="utf-8")
    attacker_payload = write_policy(attacker, "t2")
    initial = access.load_recording_policy(path)
    assert (initial is not None) == original_valid

    actual_open = os.open
    swapped = []

    def swapped_open(name, *args, **kwargs):
        # Simula um processo trocando o caminho por um symlink exatamente
        # depois que o FD legítimo foi aberto e antes do fstat/read.
        descriptor = actual_open(name, *args, **kwargs)
        if os.fspath(name) == os.fspath(path) and not swapped:
            path.rename(backup)
            path.symlink_to(attacker)
            swapped.append(True)
        return descriptor

    monkeypatch.setattr(access.os, "open", swapped_open)
    observed = access.load_recording_policy(path)
    assert swapped
    if original_valid:
        assert observed == initial
        assert observed != attacker_payload
    else:
        assert observed is None
    assert path.is_symlink()


def test_policy_growth_during_read_is_bounded(monkeypatch, tmp_path):
    path = tmp_path / "catalog.json"
    write_policy(path)
    actual_fdopen = os.fdopen
    grown = []

    def grow_before_read(fd, *args, **kwargs):
        stream = actual_fdopen(fd, *args, **kwargs)
        if not grown:
            with path.open("ab") as handle:
                handle.write(b" " * (access.MAX_POLICY_BYTES + 10))
            grown.append(True)
        return stream

    monkeypatch.setattr(access.os, "fdopen", grow_before_read)
    assert access.load_recording_policy(path) is None
    assert grown


def test_policy_revocation_is_visible_between_reads(tmp_path):
    path = tmp_path / "catalog.json"
    write_policy(path)
    assert access.load_recording_policy(path) is not None
    path.write_text("{}", encoding="utf-8")
    assert access.load_recording_policy(path) is None
