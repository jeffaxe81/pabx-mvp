#!/bin/sh
# Roda dentro do container pabx-backup (docker-compose.yml). Empacota
# tudo que foi montado em /pabx (configs + dados de negócio dos
# volumes Docker) num .tar.gz com timestamp, e chama a limpeza de
# retenção logo em seguida.
set -eu

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
ARCHIVE="/backups/pabx-backup-${TIMESTAMP}.tar.gz"

tar czf "$ARCHIVE" -C / pabx

echo "[backup] criado: $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"

python3 /pabx-scripts/retention.py /backups "${BACKUP_RETENTION_DAYS:-0}"
