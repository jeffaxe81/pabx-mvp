#!/usr/bin/env python3
"""REL-17: prova isolada do rollback real de arquivos e volumes Docker.

Usa SOMENTE volumes efêmeros com nomes exclusivos. Nunca altera volumes da
instalação AXE e nunca se conecta a uma operadora ou serviço de produção.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
DIRS = ("asterisk", "admin", "webphone", "provisioning", "recordings")
DATA = {"admin_data": "cadastro-sintetico-t1", "queue_api_data": "historico-sintetico-t2"}
FILES = ("docker-compose.yml", "prompt-base-pabx.md")
IMAGE = "alpine:3.21.4"
PHASE = "initial"


def command(args, **kwargs):
    result = subprocess.run(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        timeout=90, check=False, **kwargs
    )
    if result.returncode:
        # Não expor qualquer valor incidental de stdout/stderr do Docker/backup.
        raise RuntimeError("etapa isolada falhou: " + str(args[0]))
    return result.stdout


def docker(*args):
    return command(["docker", *args])


def volume_marker(name):
    return docker("run", "--rm", "-v", name + ":/data", IMAGE, "cat", "/data/proof.txt").strip()


def copy_volume_to_host(name, target):
    docker("run", "--rm", "-v", name + ":/data:ro", "-v", str(target) + ":/backup",
           IMAGE, "sh", "-c", "cp -a /data/. /backup/")


def restore_volume(name, source):
    docker("run", "--rm", "-v", name + ":/data", "-v", str(source) + ":/backup:ro",
           IMAGE, "sh", "-c", "rm -f /data/proof.txt && cp -a /backup/. /data/")


def run_lab():
    global PHASE
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("execução restrita ao runner GitHub Actions")
    # Identificadores não coincidem com os volumes reais do docker-compose.
    suffix = uuid.uuid4().hex[:20]
    names = {k: "axe-rel17-lab-" + suffix + "-" + k.replace("_", "-") for k in DATA}
    created = []
    status = {"sandbox_only": True, "backup_validated": False,
              "files_restored": False, "docker_volumes_restored": False,
              "negative_confirmation": False, "cleanup": False,
              "production_authorized": False}
    try:
        with tempfile.TemporaryDirectory(prefix="axe-rel17-lab-") as temp:
            temp = Path(temp)
            source = temp / "source" / "pabx"
            source.mkdir(parents=True)
            for folder in DIRS:
                d = source / folder
                d.mkdir()
                (d / "proof.txt").write_text("original-" + folder, encoding="utf-8")
            for filename in FILES:
                (source / filename).write_text("original-" + filename, encoding="utf-8")
            for label, value in DATA.items():
                PHASE = "create_volume"
                docker("volume", "create", "--label", "io.axe.pabx.lab=rel17", names[label])
                created.append(names[label])
                PHASE = "write_volume"
                docker("run", "--rm", "-v", names[label] + ":/data", IMAGE,
                       "sh", "-c", "printf '%s' '" + value + "' > /data/proof.txt")
                folder = source / label
                folder.mkdir()
                PHASE = "snapshot_volume"
                copy_volume_to_host(names[label], folder)
                if (folder / "proof.txt").read_text() != value:
                    raise RuntimeError("snapshot não corresponde ao volume original")

            backups = temp / "backups"
            backups.mkdir()
            env = dict(os.environ)
            env.update({
                "PABX_BACKUP_SOURCE_ROOT": str(temp / "source"),
                "PABX_BACKUP_DEST_DIR": str(backups),
                "PABX_BACKUP_VALIDATOR": str(ROOT / "backup/validate_archive.py"),
                "PABX_BACKUP_RETENTION": str(ROOT / "backup/retention.py"),
                "BACKUP_RETENTION_DAYS": "0",
            })
            PHASE = "backup_generate"
            command(["sh", str(ROOT / "backup/backup.sh")], env=env)
            archives = list(backups.glob("*.tar.gz"))
            if len(archives) != 1:
                raise RuntimeError("snapshot não publicado unicamente")
            archive = archives[0]
            PHASE = "backup_validate"
            command([sys.executable, str(ROOT / "backup/validate_archive.py"), str(archive)])
            status["backup_validated"] = True

            target = temp / "target"
            target.mkdir()
            for folder in DIRS:
                (target / folder).mkdir()
                (target / folder / "proof.txt").write_text("versao-nova", encoding="utf-8")
            for filename in FILES:
                (target / filename).write_text("versao-nova", encoding="utf-8")
            tmpdir = temp / "restore-tmp"
            tmpdir.mkdir()
            restore_env = dict(env, TMPDIR=str(tmpdir))

            # Confirmação negativa: não pode sobrescrever arquivo algum.
            PHASE = "restore_decline"
            deny = subprocess.run(
                ["sh", str(ROOT / "backup/restore.sh"), str(archive)],
                cwd=target, input="nao\n", text=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=90, env=restore_env, check=False,
            )
            status["negative_confirmation"] = (
                deny.returncode != 0
                and (target / "asterisk/proof.txt").read_text() == "versao-nova"
            )
            if not status["negative_confirmation"]:
                raise RuntimeError("cancelamento do rollback falhou")
            PHASE = "restore_confirm"
            command(["sh", str(ROOT / "backup/restore.sh"), str(archive)],
                    cwd=target, input="sim\n", env=restore_env)
            status["files_restored"] = all(
                (target / folder / "proof.txt").read_text() == "original-" + folder
                for folder in DIRS
            ) and all(
                (target / filename).read_text() == "original-" + filename
                for filename in FILES
            )
            if not status["files_restored"]:
                raise RuntimeError("rollback dos arquivos incompleto")

            # Os volumes reais são zerados e restaurados com comandos Docker,
            # reproduzindo a etapa MANUAL documentada, sem usar nomes reais.
            PHASE = "volume_mutate"
            for label, value in DATA.items():
                docker("run", "--rm", "-v", names[label] + ":/data", IMAGE,
                       "sh", "-c", "printf '%s' 'estado-novo' > /data/proof.txt")
            staging = temp / "staging"
            staging.mkdir()
            PHASE = "archive_extract"
            with tarfile.open(archive, "r:gz") as tar:
                tar.extractall(staging, filter="data")
            for label, value in DATA.items():
                if volume_marker(names[label]) != "estado-novo":
                    raise RuntimeError("mutação de volume não ocorreu")
                PHASE = "archive_volume_data"
                volume_path = staging / "pabx" / label
                if (volume_path / "proof.txt").read_text() != value:
                    raise RuntimeError("dados divergentes no arquivo restaurável")
                PHASE = "volume_restore_command"
                restore_volume(names[label], volume_path)
                PHASE = "volume_restore_verify"
                observed = volume_marker(names[label])
                if observed != value:
                    PHASE = ("volume_restore_verify_old_state" if observed == "estado-novo"
                             else "volume_restore_verify_empty" if not observed
                             else "volume_restore_verify_other")
                    raise RuntimeError("restauração de volume divergente")
            status["docker_volumes_restored"] = True
    finally:
        for name in reversed(created):
            # Cada nome foi gerado exclusivamente neste processo.
            subprocess.run(["docker", "volume", "rm", name], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=30, check=False)
        status["cleanup"] = all(
            subprocess.run(["docker", "volume", "inspect", name],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=15, check=False).returncode != 0
            for name in created
        )
    if not all(status[k] for k in (
        "sandbox_only", "backup_validated", "files_restored",
        "docker_volumes_restored", "negative_confirmation", "cleanup"
    )):
        raise RuntimeError("provas incompletas")
    return status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    report = {"kind": "rel17_real_docker_volume_rollback_isolated",
              "operational_go_authorized": False, "success": False}
    try:
        report.update(run_lab())
        report["success"] = True
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        # Saída sanitizada: não incluir saída de comando nem nomes de volume.
        report["error_type"] = type(exc).__name__
        report["failed_phase"] = PHASE
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("REL-17 volumes Docker isolados:", "OK" if report["success"] else "FALHOU", report.get("failed_phase", ""))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
