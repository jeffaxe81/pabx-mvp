# Manual 84 — Emissão e revogação de credenciais de gravações

## Objetivo

O Manual 80 introduziu Bearer com tenant, papel, expiração e
verificação de hash, mas a emissão e revogação eram manuais no JSON.
O utilitário local \`queue-api/recording_credentials.py\` evita a
edição direta da lista de credenciais. Não altera o catálogo de
áudios nem concede uma identidade SSO.

## Segurança antes de utilizar

- Use console autorizado, em servidor local com acesso exclusivo ao
  volume privado \`queue_api_data\`.
- A política deve existir, ser válida e ter modo \`0600\`.
- Evite copiar tokens para logs, histórico de terminal, CI, e-mail
  ou repositório. O token é **exibido apenas uma vez**, na saída de
  emissão; ao listar é mostrado apenas o SHA-256.
- Não use o console a partir de uma estação sem controle de acesso;
  use HTTPS e proxy confiável para transferir o token ao Webphone.

## Comandos

\`\`\`bash
# Emitir um token de supervisor, válido por 1 hora:
python3 queue-api/recording_credentials.py \
  --policy /local/privado/recording_access.json \
  issue --tenant t1 --role supervisor --ttl 3600

# Token de agente associado a um único ramal:
python3 queue-api/recording_credentials.py \
  --policy /local/privado/recording_access.json \
  issue --tenant t1 --role agent \
  --extension t1-recepcao --ttl 1800

# Metadados, nunca o token em claro:
python3 queue-api/recording_credentials.py \
  --policy /local/privado/recording_access.json list

# Revogar por SHA-256 completo da saída do comando list:
python3 queue-api/recording_credentials.py \
  --policy /local/privado/recording_access.json \
  revoke --sha256 <64 caracteres hexadecimais>
\`\`\`

TTL permitido: 300 a 86400 segundos, sem extensão para papéis admin
ou supervisor. Papéis: admin, supervisor, agent. Um agente precisa
ter \`extension\` com prefixo do tenant; os endpoints continuam a
validar vínculo por gravação e tenant no catálogo.

O utilitário guarda somente SHA-256, aplica lock exclusivo entre
processos e usa escrita atômica. Revogação entra em vigor na próxima
verificação HTTP porque o servidor recarrega a política por pedido;
requisições já atendidas não podem ser retroativamente canceladas.

## Testes

\`\`\`bash
(cd queue-api && python3 -m pytest -q tests/test_recording_credentials.py)
\`\`\`

Verifica emissão, expiração, hash, revogação, preservação do catálogo,
limites de TTL e de quantidade, e recusa de papéis/tenants inseguros.

## Limitações

O acesso ao arquivo e ao console substitui a autorização
administrativa de emissão. Ainda falta integrar o serviço ao login
do painel, auditoria de operadores, inventário e aprovação de acesso
por empresa. **Não é homologação real de Asterisk, SIP ou de gravação.**
