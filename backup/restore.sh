#!/bin/sh
# Rode isso NO HOST (não dentro de um container), na raiz do projeto
# (onde fica o docker-compose.yml), depois de "docker compose down".
#
# Uso:
#   sh backup/restore.sh backups/pabx-backup-AAAAMMDD-HHMMSS.tar.gz
set -eu

ARCHIVE="${1:-}"
if [ -z "$ARCHIVE" ]; then
  echo "Uso: $0 <arquivo-de-backup.tar.gz>"
  exit 1
fi
if [ ! -f "$ARCHIVE" ]; then
  echo "Arquivo não encontrado: $ARCHIVE"
  exit 1
fi

echo "Isso sobrescreve asterisk/, admin/, webphone/, provisioning/,"
echo "recordings/ e docker-compose.yml com o conteúdo do backup."
echo "Confirme que já rodou 'docker compose down' antes de continuar."
printf "Continuar? (digite 'sim' para confirmar): "
read CONFIRM
if [ "$CONFIRM" != "sim" ]; then
  echo "Cancelado."
  exit 1
fi

TMP_DIR=$(mktemp -d)
tar xzf "$ARCHIVE" -C "$TMP_DIR"

cp -r "$TMP_DIR/pabx/asterisk/." ./asterisk/
cp -r "$TMP_DIR/pabx/admin/." ./admin/
cp -r "$TMP_DIR/pabx/webphone/." ./webphone/
cp -r "$TMP_DIR/pabx/provisioning/." ./provisioning/
cp -r "$TMP_DIR/pabx/recordings/." ./recordings/
cp "$TMP_DIR/pabx/docker-compose.yml" ./docker-compose.yml
cp "$TMP_DIR/pabx/prompt-base-pabx.md" ./prompt-base-pabx.md

echo ""
echo "Arquivos e configs restaurados."
echo ""
echo "FALTA UM PASSO MANUAL: os dados dos volumes Docker (usuários do"
echo "painel de administração, ramais cadastrados dinamicamente,"
echo "histórico de relatórios) precisam ser restaurados separadamente,"
echo "porque este script não tem acesso ao socket do Docker de propósito"
echo "(ver manual 28 sobre essa decisão). Rode:"
echo ""
echo "  docker volume create pabx-mvp_admin_data 2>/dev/null || true"
echo "  docker volume create pabx-mvp_queue_api_data 2>/dev/null || true"
echo "  docker run --rm -v pabx-mvp_admin_data:/data -v ${TMP_DIR}/pabx/admin_data:/backup:ro alpine sh -c 'rm -rf /data/* && cp -r /backup/. /data/'"
echo "  docker run --rm -v pabx-mvp_queue_api_data:/data -v ${TMP_DIR}/pabx/queue_api_data:/backup:ro alpine sh -c 'rm -rf /data/* && cp -r /backup/. /data/'"
echo ""
echo "Depois disso: docker compose up -d"
echo ""
echo "(o diretório temporário $TMP_DIR não é apagado automaticamente -"
echo " remova manualmente depois de confirmar que os comandos acima rodaram)"
