"""Prova de expurgo controlado com WAV criado pelo MixMonitor real.

O WAV fonte permanece no Asterisk descartável. Só a cópia privada
passa pelo expurgo; nenhum áudio, token ou nome opaco aparece no relatório.
"""
import os
from pathlib import Path
import shutil
import stat
import sys
import time

from .recording_checks import TENANTS
from .recording_http_checks import _read_lab_wav

METRICS = ("source_wav_valid", "retention_opt_in",
           "expired_deleted", "recent_preserved",
           "non_audio_preserved", "symlink_denied",
           "source_unchanged")


def required_retention_checks():
    return {f"retention_{metric}:{tenant}" for tenant in TENANTS
            for metric in METRICS}


def inspect_retention_copy(folder, source, *, clock):
    """Opera em arquivos regulares locais, nunca na fonte original."""
    api = str(Path(__file__).resolve().parents[1] / "queue-api")
    if api not in sys.path:
        sys.path.insert(0, api)
    from recordings import delete_expired_recordings, list_recordings

    folder = Path(folder)
    source = Path(source)
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError("diretório privado de retenção inválido")
    audio = _read_lab_wav(source)
    stat_before = source.stat()
    if not stat.S_ISREG(stat_before.st_mode) or stat_before.st_nlink != 1:
        raise ValueError("WAV original não é inode regular exclusivo")
    recent = folder / "recent.wav"
    expired = folder / "expired.wav"
    note = folder / "protected.txt"
    linked = folder / "linked.wav"
    for target in (recent, expired):
        if target.exists() or target.is_symlink():
            raise ValueError("artefato duplicado")
        shutil.copyfile(source, target)
        target.chmod(0o600)
    note.write_text("KEEP", encoding="ascii")
    note.chmod(0o600)
    os.utime(recent, (clock - 5 * 86400, clock - 5 * 86400))
    os.utime(expired, (clock - 31 * 86400, clock - 31 * 86400))
    linked.symlink_to(source)
    checks = {
        "source_wav_valid": _read_lab_wav(recent) == audio
                            and _read_lab_wav(expired) == audio,
        "retention_opt_in": delete_expired_recordings(
            folder, retention_days=0, clock=lambda: clock
        ) == [] and recent.exists() and expired.exists(),
    }
    deleted = delete_expired_recordings(
        folder, retention_days=30, clock=lambda: clock)
    checks.update({
        "expired_deleted": deleted == ["expired.wav"] and not expired.exists(),
        "recent_preserved": recent.exists()
                            and _read_lab_wav(recent) == audio
                            and {entry["filename"] for entry in list_recordings(
                                folder, limit=10)} == {"recent.wav"},
        "non_audio_preserved": note.read_text(encoding="ascii") == "KEEP",
        "symlink_denied": linked.is_symlink()
                          and linked.resolve() == source.resolve(),
        "source_unchanged": source.stat().st_ino == stat_before.st_ino
                            and source.stat().st_size == stat_before.st_size
                            and _read_lab_wav(source) == audio,
    })
    return checks


def exercise_retention(container, prepared, report):
    from .asterisk_lab import command

    checks = report["checks"]
    checks.update({name: False for name in required_retention_checks()})
    report["real_wav_retention_tested"] = False
    names = prepared.get("lab_recording_filenames")
    if not isinstance(names, dict) or set(names) != set(TENANTS):
        raise ValueError("arquivos MixMonitor não preparados")
    staging = Path(prepared["conf"]).parent / "retention-private-lab"
    staging.mkdir(mode=0o700, exist_ok=False)
    sources = staging / "sources"
    sources.mkdir(mode=0o700)
    now = time.time()
    for tenant in TENANTS:
        report["phase"] = "retention:" + tenant
        sub = staging / tenant
        sub.mkdir(mode=0o700)
        source = sources / (tenant + ".wav")
        command(["docker", "cp", container + ":/var/spool/asterisk/monitor/"
                 + tenant + "/" + names[tenant], str(source)], timeout=20)
        source.chmod(0o600)
        outputs = inspect_retention_copy(sub, source, clock=now)
        for metric in METRICS:
            checks[f"retention_{metric}:{tenant}"] = outputs[metric] is True
        report.setdefault("retention_cases", {})[tenant] = {
            "real_mixmonitor_source": checks[f"retention_source_wav_valid:{tenant}"],
            "expired_only": checks[f"retention_expired_deleted:{tenant}"],
            "newer_preserved": checks[f"retention_recent_preserved:{tenant}"],
            "original_unchanged": checks[f"retention_source_unchanged:{tenant}"],
        }
    report["real_wav_retention_tested"] = all(
        checks[key] is True for key in required_retention_checks()
    )
    if not report["real_wav_retention_tested"]:
        raise ValueError("expurgo seguro de WAV do MixMonitor não comprovado")
