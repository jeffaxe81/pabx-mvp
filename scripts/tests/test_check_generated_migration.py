import json
from pathlib import Path

import pytest
from check_generated_migration import STATIC_FILES, STATIC_INCLUDES, inspect, main


def fixture_tree(tmp_path, with_t3=False):
    root = tmp_path / "asterisk"
    generated = root / "generated"
    generated.mkdir(parents=True)
    for name in STATIC_FILES:
        (generated / name).write_text(f"; generated {name}\n", encoding="utf-8")
    for conf, names in STATIC_INCLUDES.items():
        (root / conf).write_text(
            "".join(f"#include generated/{name}\n" for name in names),
            encoding="utf-8",
        )
    registry = tmp_path / "tenants.json"
    registry.write_text(
        json.dumps([{"tenant_id": "t3", "did": "SENSITIVE"}] if with_t3 else []),
        encoding="utf-8",
    )
    if with_t3:
        for name in (
            "extensions_dynamic_dial-t3.conf",
            "extensions_dynamic_hints-t3.conf",
            "voicemail_dynamic_t3.conf",
        ):
            (generated / name).write_text("; generated\n", encoding="utf-8")
    return root, registry


def test_baseline_complete_and_no_operational_claims(tmp_path):
    root, registry = fixture_tree(tmp_path)
    report = inspect(root, registry)
    assert report["ready_for_runtime_verification"]
    assert report["percent"] == 100
    assert not report["docker_mount_checked"]
    assert not report["asterisk_reload_checked"]
    assert not report["sip_call_tested"]


def test_tenant_dynamic_files_checked_without_exposing_did(tmp_path):
    root, registry = fixture_tree(tmp_path, with_t3=True)
    report = inspect(root, registry)
    assert report["ready_for_runtime_verification"]
    assert report["checked_tenants"] == ["t3"]
    assert "SENSITIVE" not in json.dumps(report)
    (root / "generated" / "voicemail_dynamic_t3.conf").unlink()
    report = inspect(root, registry)
    assert not report["ready_for_runtime_verification"]
    assert report["checks"]["generated:voicemail_dynamic_t3.conf"] == "missing_or_unsafe"


def test_detects_old_include_and_blank_config(tmp_path):
    root, registry = fixture_tree(tmp_path)
    (root / "pjsip.conf").write_text("#include pjsip_dynamic.conf\n")
    (root / "generated" / "pjsip_dynamic.conf").write_text("")
    result = inspect(root, registry)
    assert not result["ready_for_runtime_verification"]
    assert result["checks"]["include:pjsip.conf:pjsip_dynamic.conf"] == "missing_include"
    assert result["checks"]["generated:pjsip_dynamic.conf"] == "empty"


def test_legacy_compare_blocks_different_file_and_accepts_copied_file(tmp_path):
    root, registry = fixture_tree(tmp_path)
    old = root / "pjsip_dynamic.conf"
    old.write_text("old production config", encoding="utf-8")
    report = inspect(root, registry, compare_legacy=True)
    assert not report["ready_for_runtime_verification"]
    assert report["checks"]["legacy_match:pjsip_dynamic.conf"] == "different"
    (root / "generated" / "pjsip_dynamic.conf").write_bytes(old.read_bytes())
    report = inspect(root, registry, compare_legacy=True)
    assert report["ready_for_runtime_verification"]
    assert report["checks"]["legacy_match:pjsip_dynamic.conf"] == "ok"


def test_rejects_tenant_registry_with_invalid_ids_and_duplicates(tmp_path):
    root, registry = fixture_tree(tmp_path)
    for bad in (
        [{"tenant_id": "../t3"}],
        [{"tenant_id": "t3"}, {"tenant_id": "t3"}],
        [{"tenant_id": "t1"}],
        {"tenant_id": "t3"},
    ):
        registry.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(ValueError):
            inspect(root, registry)


def test_rejects_generated_symlink(tmp_path):
    root, registry = fixture_tree(tmp_path)
    generated = root / "generated"
    (root / "fake").mkdir()
    # A substituição de um diretório válido por symlink não é aceita.
    for name in STATIC_FILES:
        (generated / name).unlink()
    generated.rmdir()
    generated.symlink_to(root / "fake")
    with pytest.raises(ValueError, match="generated"):
        inspect(root, registry)


def test_readonly_cli_reports_status_and_exit_codes(tmp_path, capsys):
    root, registry = fixture_tree(tmp_path)
    args = ["--asterisk-dir", str(root), "--tenant-registry", str(registry)]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["percent"] == 100
    (root / "generated" / STATIC_FILES[0]).unlink()
    assert main(args) == 1
    assert not json.loads(capsys.readouterr().out)["ready_for_runtime_verification"]


def test_legacy_compare_absent_files_do_not_block_fresh_install(tmp_path):
    root, registry = fixture_tree(tmp_path)
    result = inspect(root, registry, compare_legacy=True)
    assert result["ready_for_runtime_verification"]
    assert result["checks"]["legacy_match:pjsip_dynamic.conf"] == "no_legacy_file"
