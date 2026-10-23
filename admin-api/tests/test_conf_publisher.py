"""Testes offline de lote de .conf e compensação AMI em falha."""
from pathlib import Path
import stat

import pytest

import conf_publisher
from conf_publisher import published_conf_batch
import server


def test_publish_valid_conf_batch_replaces_all_files(tmp_path):
    a = tmp_path / "pjsip_dynamic.conf"
    a.write_text("antigo", encoding="utf-8")
    with published_conf_batch(tmp_path, {
        "pjsip_dynamic.conf": "novo",
        "extensions_dynamic_dial-t3.conf": "tres",
    }):
        assert a.read_text(encoding="utf-8") == "novo"
    assert a.read_text(encoding="utf-8") == "novo"
    assert (tmp_path / "extensions_dynamic_dial-t3.conf").read_text() == "tres"
    assert not list(tmp_path.glob(".pabx-conf-*"))


def test_publish_preserves_existing_conf_file_permissions(tmp_path):
    target = tmp_path / "pjsip_dynamic.conf"
    target.write_text("old", encoding="utf-8")
    target.chmod(0o640)
    with published_conf_batch(tmp_path, {"pjsip_dynamic.conf": "new"}):
        assert stat.S_IMODE(target.stat().st_mode) == 0o640


def test_context_error_restores_previous_files_and_removes_new_files(tmp_path):
    existing = tmp_path / "pjsip_dynamic.conf"
    existing.write_bytes(b"previous-secret")
    existing.chmod(0o600)
    with pytest.raises(RuntimeError, match="AMI indisponível"):
        with published_conf_batch(tmp_path, {
            "pjsip_dynamic.conf": "new-secret",
            "voicemail_dynamic_t3.conf": "new-voicemail",
        }):
            raise RuntimeError("AMI indisponível")
    assert existing.read_bytes() == b"previous-secret"
    assert stat.S_IMODE(existing.stat().st_mode) == 0o600
    assert not (tmp_path / "voicemail_dynamic_t3.conf").exists()
    assert not list(tmp_path.glob(".pabx-conf-*"))


def test_midbatch_replace_error_restores_already_published_config(tmp_path, monkeypatch):
    old = tmp_path / "pjsip_dynamic.conf"
    old.write_text("old", encoding="utf-8")
    real_replace = conf_publisher.os.replace
    calls = []

    def fail_second(source, destination):
        calls.append(str(destination))
        if len(calls) == 2:
            raise OSError("disco desconectado")
        return real_replace(source, destination)

    monkeypatch.setattr(conf_publisher.os, "replace", fail_second)
    with pytest.raises(OSError, match="disco desconectado"):
        with published_conf_batch(tmp_path, {
            "pjsip_dynamic.conf": "new",
            "voicemail_dynamic_t3.conf": "new",
        }):
            pass
    assert old.read_text(encoding="utf-8") == "old"
    assert not (tmp_path / "voicemail_dynamic_t3.conf").exists()
    assert not list(tmp_path.glob(".pabx-conf-*"))


@pytest.mark.parametrize("filename", [
    "../manager.conf", "/etc/asterisk/manager.conf",
    "file.conf\n[malicious]", "file.txt", "", "..",
])
def test_publish_rejects_unsafe_file_names_without_mutation(tmp_path, filename):
    target = tmp_path / "pjsip_dynamic.conf"
    target.write_text("safe", encoding="utf-8")
    with pytest.raises(ValueError):
        with published_conf_batch(tmp_path, {
            "pjsip_dynamic.conf": "changed", filename: "bad",
        }):
            pass
    assert target.read_text(encoding="utf-8") == "safe"
    assert not list(tmp_path.glob(".pabx-conf-*"))


def test_publish_rejects_symlink_targets(tmp_path):
    original = tmp_path / "manager.conf"
    original.write_text("private", encoding="utf-8")
    (tmp_path / "pjsip_dynamic.conf").symlink_to(original)
    with pytest.raises(ValueError, match="simbólico"):
        with published_conf_batch(tmp_path, {"pjsip_dynamic.conf": "bad"}):
            pass
    assert original.read_text(encoding="utf-8") == "private"


def test_publish_rejects_non_text_body(tmp_path):
    with pytest.raises(ValueError, match="conteúdo"):
        with published_conf_batch(tmp_path, {"pjsip_dynamic.conf": b"binary"}):
            pass
    assert not list(tmp_path.glob(".pabx-conf-*"))


def test_ami_success_commits_configs(tmp_path, monkeypatch):
    old = tmp_path / "pjsip_dynamic.conf"
    old.write_text("old", encoding="utf-8")
    monkeypatch.setattr(server, "ASTERISK_CONF_DIR", str(tmp_path))
    monkeypatch.setattr(server, "load_store", lambda path: [])
    monkeypatch.setattr(server, "known_extension_tenants", lambda: {"t1", "t2"})
    monkeypatch.setattr(server, "render_all", lambda *a, **k: {"pjsip_dynamic.conf": "new"})
    events = []

    class AMISuccess:
        def __init__(self, *args):
            pass
        def connect_and_login(self):
            events.append("connect")
        def register_extension_mapping(self, *args):
            events.append("map")
        def reload_pjsip_and_dialplan(self):
            events.append("reload")
            assert old.read_text(encoding="utf-8") == "new"
            return {k: "Follows" for k in ("pjsip", "dialplan", "voicemail", "queue", "parking")}
        def close(self):
            events.append("close")

    monkeypatch.setattr(server, "AMIClient", AMISuccess)
    report = server.regenerate_and_reload(
        [("register_extension_mapping", (1100, "agent", "t1"))]
    )
    assert report["pjsip"] == "Follows"
    assert old.read_text(encoding="utf-8") == "new"
    assert events == ["connect", "map", "reload", "close"]


def test_ami_error_restores_files_and_reloads_previous_configuration(tmp_path, monkeypatch):
    old = tmp_path / "pjsip_dynamic.conf"
    old.write_text("prior-configuration", encoding="utf-8")
    monkeypatch.setattr(server, "ASTERISK_CONF_DIR", str(tmp_path))
    monkeypatch.setattr(server, "load_store", lambda path: [])
    monkeypatch.setattr(server, "known_extension_tenants", lambda: {"t1"})
    monkeypatch.setattr(server, "render_all", lambda *a, **k: {"pjsip_dynamic.conf": "new"})
    seen = []
    class AMIError:
        def __init__(self, *args):
            pass
        def connect_and_login(self):
            pass
        def reload_pjsip_and_dialplan(self):
            seen.append(old.read_text(encoding="utf-8"))
            statuses = {k: "Follows" for k in ("pjsip", "dialplan", "voicemail", "queue", "parking")}
            if len(seen) == 1:
                statuses["dialplan"] = "Error"
            return statuses
        def close(self):
            pass

    monkeypatch.setattr(server, "AMIClient", AMIError)
    with pytest.raises(RuntimeError, match="não confirmou"):
        server.regenerate_and_reload()
    assert seen == ["new", "prior-configuration"]
    assert old.read_text(encoding="utf-8") == "prior-configuration"
