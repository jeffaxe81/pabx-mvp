#!/bin/sh
# Backup atômico: não publica arquivo incompleto nem executa retenção
# antes de verificar a leitura e a estrutura mínima do arquivo.
set -eu

SOURCE_ROOT="${PABX_BACKUP_SOURCE_ROOT:-/}"
BACKUP_DIR="${PABX_BACKUP_DEST_DIR:-/backups}"
VALIDATOR="${PABX_BACKUP_VALIDATOR:-/pabx-scripts/validate_archive.py}"
RETENTION="${PABX_BACKUP_RETENTION:-/pabx-scripts/retention.py}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
ARCHIVE="${BACKUP_DIR}/pabx-backup-${TIMESTAMP}.tar.gz"
PARTIAL="${ARCHIVE}.partial.$$"
trap 'rm -f "$PARTIAL"' EXIT HUP INT TERM

tar czf "$PARTIAL" -C "$SOURCE_ROOT" pabx
python3 "$VALIDATOR" "$PARTIAL"
mv -n "$PARTIAL" "$ARCHIVE"
if [ -e "$PARTIAL" ]; then
  echo "[backup] colisão no nome do arquivo: $ARCHIVE" >&2
  exit 1
fi

echo "[backup] criado e validado: $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"
python3 "$RETENTION" "$BACKUP_DIR" "${BACKUP_RETENTION_DAYS:-0}"
