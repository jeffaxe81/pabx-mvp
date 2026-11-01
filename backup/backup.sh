#!/bin/sh
# Backup atômico: não publica arquivo incompleto nem executa retenção
# antes de verificar a leitura e a estrutura mínima do arquivo.
set -eu

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
ARCHIVE="/backups/pabx-backup-${TIMESTAMP}.tar.gz"
PARTIAL="${ARCHIVE}.partial.$$"
trap 'rm -f "$PARTIAL"' EXIT HUP INT TERM

tar czf "$PARTIAL" -C / pabx
python3 /pabx-scripts/validate_archive.py "$PARTIAL"
mv -n "$PARTIAL" "$ARCHIVE"
if [ -e "$PARTIAL" ]; then
  echo "[backup] colisão no nome do arquivo: $ARCHIVE" >&2
  exit 1
fi

echo "[backup] criado e validado: $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"
python3 /pabx-scripts/retention.py /backups "${BACKUP_RETENTION_DAYS:-0}"
