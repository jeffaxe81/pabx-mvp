"""
Testes estáticos dos scripts de backup/restauração (backlog #33).
Os scripts em si são shell/infra - não dá pra testar automaticamente
sem subir o ambiente Docker de verdade (mesma situação já documentada
pro resto das integrações deste projeto). O que dá pra garantir aqui
é que os arquivos existem, são executáveis, e contêm as
salvaguardas certas.
"""
import os
import stat
from pathlib import Path

BACKUP_DIR = Path(__file__).parent.parent / "backup"


def test_backup_and_restore_scripts_exist_and_are_executable():
    for filename in ("backup.sh", "restore.sh"):
        path = BACKUP_DIR / filename
        assert path.is_file(), f"{filename} não encontrado"
        mode = path.stat().st_mode
        assert mode & stat.S_IXUSR, f"{filename} não está marcado como executável"


def test_backup_script_calls_retention_after_archiving():
    content = (BACKUP_DIR / "backup.sh").read_text(encoding="utf-8")
    tar_pos = content.index("tar czf")
    retention_pos = content.index("retention.py")
    assert tar_pos < retention_pos, "backup.sh deveria arquivar antes de rodar a retenção"


def test_backup_script_retention_disabled_by_default_via_env_fallback():
    content = (BACKUP_DIR / "backup.sh").read_text(encoding="utf-8")
    assert '${BACKUP_RETENTION_DAYS:-0}' in content


def test_restore_script_requires_explicit_confirmation():
    """
    Restaurar backup sobrescreve arquivos de verdade - o script não
    pode simplesmente rodar sem uma confirmação explícita do operador.
    """
    content = (BACKUP_DIR / "restore.sh").read_text(encoding="utf-8")
    assert "Continuar?" in content
    assert '"sim"' in content or "'sim'" in content


def test_restore_script_documents_manual_volume_restoration_step():
    """
    O restore.sh não mexe no socket do Docker (mesma decisão de
    segurança do backup.sh) - por isso ele PRECISA deixar explícito
    que os volumes nomeados exigem um passo manual, senão a pessoa
    acha que restaurou tudo e não restaurou.
    """
    content = (BACKUP_DIR / "restore.sh").read_text(encoding="utf-8")
    assert "docker run" in content
    assert "admin_data" in content
    assert "queue_api_data" in content
