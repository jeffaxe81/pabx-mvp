#!/usr/bin/env bash
# Verificacao nao destrutiva de pre-requisitos para homologacao SIP.
# Nao modifica AstDB, nao executa reload e nao origina chamadas.
set -euo pipefail
ASTERISK_BIN="${ASTERISK_BIN:-asterisk}"
command -v "$ASTERISK_BIN" >/dev/null || { echo "ERRO: asterisk indisponivel" >&2; exit 2; }
run() { "$ASTERISK_BIN" -rx "$1"; }
check_context() {
  local ctx="$1" output
  output="$(run "dialplan show $ctx")"
  # Asterisk CLI: [ Context 'nome' created by ... ]; mocks: [nome].
  if ! grep -Fq "[$ctx]" <<<"$output" && ! grep -Fq "[ Context '$ctx'" <<<"$output"; then
    echo "FALHA: contexto $ctx ausente" >&2
    exit 1
  fi
  printf 'OK contexto %s\n' "$ctx"
}
check_context politica-externa
check_context t1-internal
check_context t2-internal
echo "Politicas atuais (somente leitura):"
for tenant in t1 t2; do
  if ! value="$(run "database get politica-externa-$tenant internacional")"; then
    echo "ERRO: falha ao consultar AstDB do tenant $tenant" >&2
    exit 1
  fi
  printf '%s: %s\n' "$tenant" "$value"
done
echo "Pre-requisitos consultados. PENDENTE: executar chamadas SIP reais, verificar CDR e rollback."
