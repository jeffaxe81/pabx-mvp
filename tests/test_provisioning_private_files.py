"""Arquivos SIP privados em disco, inclusive durante publicacao e migracao."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

import pytest

from provisioning import generate as gen

MAC = "aabbccddeeff"
OTHER_MAC = "001122334455"


@pytest.fixture
def source(tmp_path, monkeypatch):
    catalog = tmp_path / "devices.json"
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "yealink.cfg.tpl").write_text(
        "user={{RAMAL}}\nname={{NOME}}\npassword={{SENHA}}\nserver={{SERVIDOR}}\n")
    catalog.write_text(json.dumps({"devices": [{
        "mac": MAC, "vendor": "yealink", "ramal": "t1-1001",
        "nome": "Teste", "senha": "SIP-TEST-SECRET", "servidor": "pabx.local",
    }]}))
    output = tmp_path / "files"
    monkeypatch.setattr(gen, "DEVICES_FILE", str(catalog))
    monkeypatch.setattr(gen, "TEMPLATES_DIR", str(templates))
    monkeypatch.setattr(gen, "OUTPUT_DIR", str(output))
    return catalog, output


def test_private_files_and_directory_even_with_permissive_umask(source, capsys):
    _, output = source
    original = os.umask(0)
    try:
        gen.main()
    finally:
        os.umask(original)
    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    assert stat.S_IMODE((output / (MAC + ".cfg")).stat().st_mode) == 0o600
    assert "SIP-TEST-SECRET" in (output / (MAC + ".cfg")).read_text()
    assert "SIP-TEST-SECRET" not in capsys.readouterr().out


def test_temporary_is_private_before_atomic_publication(source, monkeypatch):
    _, output = source
    original = os.replace
    observed = []
    def verify(src, dst, **kwargs):
        info = os.stat(src, dir_fd=kwargs.get("src_dir_fd"), follow_symlinks=False)
        observed.append(stat.S_IMODE(info.st_mode))
        assert stat.S_IMODE(info.st_mode) == 0o600
        assert stat.S_IMODE(output.stat().st_mode) == 0o700
        return original(src, dst, **kwargs)
    monkeypatch.setattr(gen.os, "replace", verify)
    gen.main()
    assert observed == [0o600]


def test_existing_public_files_outside_current_batch_become_private(source):
    _, output = source
    output.mkdir(mode=0o755)
    output.chmod(0o755)
    stale = output / (OTHER_MAC + ".cfg")
    stale.write_text("OLD-SIP-SECRET")
    stale.chmod(0o644)
    gen.main()
    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    assert stat.S_IMODE(stale.stat().st_mode) == 0o600
    assert stale.read_text() == "OLD-SIP-SECRET"
    assert (output / (MAC + ".cfg")).exists()


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo", "directory"])
def test_unsafe_stale_cfg_is_rejected_before_publishing(source, tmp_path, kind):
    _, output = source
    output.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("EXTERNAL-UNCHANGED")
    outside.chmod(0o644)
    stale = output / (OTHER_MAC + ".cfg")
    if kind == "symlink":
        stale.symlink_to(outside)
    elif kind == "hardlink":
        os.link(outside, stale)
    elif kind == "fifo":
        os.mkfifo(stale)
    else:
        stale.mkdir()
    with pytest.raises(ValueError, match="PV-30"):
        gen.main()
    assert not (output / (MAC + ".cfg")).exists()
    assert outside.read_text() == "EXTERNAL-UNCHANGED"
    assert stat.S_IMODE(outside.stat().st_mode) == 0o644


def test_directory_swap_cannot_redirect_credentials_to_external_folder(source, tmp_path, monkeypatch):
    _, output = source
    preserved = tmp_path / "preserved"
    outside = tmp_path / "outside"
    outside.mkdir()
    original = os.open
    swapped = False
    def racing_open(path, flags, *args, **kwargs):
        nonlocal swapped
        if (isinstance(path, (str, bytes, os.PathLike))
                and Path(os.fsdecode(path)).name.startswith(".axe-pv-") and not swapped):
            swapped = True
            output.rename(preserved)
            output.symlink_to(outside, target_is_directory=True)
        return original(path, flags, *args, **kwargs)
    monkeypatch.setattr(gen.os, "open", racing_open)
    try:
        gen.main()
    except (ValueError, OSError):
        pass  # Falhar fechado tambem e aceitavel diante da troca.
    assert swapped, "cenario nao exercitou a abertura do temporario"
    assert list(outside.iterdir()) == []


def test_failure_keeps_old_content_and_cleans_private_temporary(source, monkeypatch):
    _, output = source
    output.mkdir()
    target = output / (MAC + ".cfg")
    target.write_text("OLD-CONTENT")
    target.chmod(0o644)
    def fail(*args, **kwargs):
        raise OSError("simulated disk error")
    monkeypatch.setattr(gen.os, "replace", fail)
    with pytest.raises(OSError):
        gen.main()
    assert target.read_text() == "OLD-CONTENT"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert not list(output.glob(".axe-pv-*"))


def test_uppercase_mac_is_published_at_the_mtls_canonical_route(source):
    catalog, output = source
    data = json.loads(catalog.read_text())
    data["devices"][0]["mac"] = MAC.upper()
    catalog.write_text(json.dumps(data))
    gen.main()
    assert (output / (MAC + ".cfg")).is_file()
    assert not (output / (MAC.upper() + ".cfg")).exists()


def test_invalid_source_does_not_change_existing_output_permissions(source):
    catalog, output = source
    output.mkdir()
    output.chmod(0o755)
    old = output / (OTHER_MAC + ".cfg")
    old.write_text("OLD-CONTENT")
    old.chmod(0o644)
    catalog.write_text('{"devices":[{"mac":"../../outside"}]}')
    with pytest.raises(ValueError):
        gen.main()
    assert stat.S_IMODE(output.stat().st_mode) == 0o755
    assert stat.S_IMODE(old.stat().st_mode) == 0o644
    assert old.read_text() == "OLD-CONTENT"


def test_generator_refuses_directory_owned_by_another_identity(source, monkeypatch):
    _, output = source
    output.mkdir()
    output.chmod(0o755)
    uid = os.geteuid()
    monkeypatch.setattr(gen.os, "geteuid", lambda: uid + 1)
    with pytest.raises(ValueError, match="PV-30"):
        gen.main()
    assert stat.S_IMODE(output.stat().st_mode) == 0o755
    assert list(output.iterdir()) == []


def test_generator_waits_for_existing_directory_lock(source):
    import fcntl
    catalog, output = source
    output.mkdir(mode=0o700)
    root_fd = os.open(output, os.O_RDONLY | os.O_DIRECTORY)
    process = None
    try:
        fcntl.flock(root_fd, fcntl.LOCK_EX)
        script = (
            "import sys; from provisioning import generate as g; "
            "g.DEVICES_FILE=sys.argv[1]; g.OUTPUT_DIR=sys.argv[2]; "
            "print('ready',flush=True); g.main()"
        )
        process = subprocess.Popen([sys.executable, "-c", script, str(catalog), str(output)],
                                   cwd=Path(__file__).resolve().parents[1],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert process.stdout.readline().strip() == "ready"
        with pytest.raises(subprocess.TimeoutExpired):
            process.communicate(timeout=1)
        assert not (output / (MAC + ".cfg")).exists()
        fcntl.flock(root_fd, fcntl.LOCK_UN)
        _, error = process.communicate(timeout=10)
        assert process.returncode == 0, error
        assert (output / (MAC + ".cfg")).is_file()
    finally:
        os.close(root_fd)
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate(timeout=5)
