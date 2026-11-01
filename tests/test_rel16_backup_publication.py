"""Backup só publica arquivo validado e preserva backups anteriores."""
from pathlib import Path

SCRIPT = (Path(__file__).resolve().parents[1] / "backup/backup.sh").read_text(encoding="utf-8")


def test_publicacao_ocorre_apos_validacao():
    assert SCRIPT.index('tar czf "$PARTIAL"') < SCRIPT.index("validate_archive.py")
    assert SCRIPT.index("validate_archive.py") < SCRIPT.index('mv -n "$PARTIAL" "$ARCHIVE"')
    assert SCRIPT.index('mv -n "$PARTIAL" "$ARCHIVE"') < SCRIPT.index("retention.py")


def test_arquivo_parcial_e_removido_em_falha():
    assert 'trap ' in SCRIPT
    assert 'rm -f "$PARTIAL"' in SCRIPT


def test_retencao_desabilitada_por_padrao():
    assert '${BACKUP_RETENTION_DAYS:-0}' in SCRIPT
