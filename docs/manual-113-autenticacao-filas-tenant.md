# Manual 113 — Credenciais e visibilidade das filas por empresa

## Proteção (Marco 8 parcial)

Antes deste incremento, `GET /api/queue` expunha a lista inteira de
chamadas recebidas pelo AMI, e `POST /api/queue/pickup` só verificava
o ramal informado pelo próprio solicitante. Agora ambas exigem token
Bearer válido, com tenant/papel e vencimento, por catálogo independente
da política de gravações.

- `GET /api/queue`: retorna exclusivamente itens das filas
  `fila-tN`, `fila-tN-en` ou `fila-tN-es` cujo **tenant exato**
  é igual ao registrado na credencial. Nome alterado na query string
  não dá acesso a outra empresa. Prefixos `t1` e `t10` não se confundem.
- `POST /api/queue/pickup`: valida a mesma identidade, depois exige
  ramal na allowlist e na mesma empresa da fila originada do AMI.
  Usuários `agent` só atuam no próprio ramal; `admin`/`supervisor`
  podem atuar em outros ramais permitidos **da sua empresa**.
- Política ausente, expirada, inválida, com permissões abertas ou por
  symlink: acesso negado (**HTTP 401**). Origem HTTP de navegador não
  explicitamente permitida: **HTTP 403**, inclusive preflight OPTIONS.
  Não há CORS `*` nas duas rotas protegidas. Respostas têm `no-store`.
- Corrigido o prefixo amplo que antes retornava filas até em URLs
  como `/api/queueXYZ`; somente `/api/queue` é consulta válida.

## Como habilitar no servidor controlado

1. Restrinja a porta 8090 por firewall ou proxy autenticado e configure
   HTTPS/TLS real para acesso remoto; CORS **não é autenticação**.
2. Na configuração `docker-compose.yml`, configure
   `QUEUE_CORS_ORIGINS` com a **origem exata**, por exemplo
   `https://pabx.exemplo.com`, e preserve o catálogo dentro do
   volume privado `queue_api_data`.
3. Inicialize sem sobrescrever arquivo existente:

   ```bash
   docker compose exec queue-api python3 queue_credentials.py \
     --policy /app/data/queue_access.json init
   ```

4. Emita uma credencial de agente que expire em uma hora:

   ```bash
   docker compose exec queue-api python3 queue_credentials.py \
     --policy /app/data/queue_access.json issue \
     --tenant t1 --role agent --extension t1-recepcao --ttl 3600
   ```

   Para supervisor, use `--role supervisor` sem `--extension`. A CLI
   mostra o token **uma única vez**, no console privado, e guarda apenas
   seu SHA-256. Não registre a saída em logs ou versionamento.
5. Informe esse token no campo **Credencial temporária da fila** do
   Webphone ou do painel operacional. Não o coloque no endereço/URL,
   configuração JavaScript, localStorage, sessionStorage ou link enviado.
   O Webphone exige HTTPS (ou localhost) e usa cabeçalho
   `Authorization: Bearer`.
6. Para revogar, use somente o hash informado na emissão:

   ```bash
   docker compose exec queue-api python3 queue_credentials.py \
     --policy /app/data/queue_access.json revoke \
     --sha256 HASH_SHA256_EXATO_DA_CREDENCIAL
   ```

   A próxima requisição já releitura a política, sem reinicialização.

## Evidências automatizadas

- `queue-api/tests/test_queue_auth_http.py`: HTTP real em localhost,
  AMI simulado, cenários de t1/t2/t10, expiração, negação anônima,
  CORS, query falsificada, troca de token, papel do agente e URL
  ambígua.
- `queue-api/tests/test_queue_credentials.py`: arquivo privado,
  emissão/revogação atômicas, TTL, symlink, colisão de tenant e schema.
- `queue-api/tests/test_pickup_tenant_boundary.py`: atualizados os
  clientes de teste para o novo Bearer; permanecem negativos de
  redirecionamento entre empresas.

## Limitações — sem GO

O token é uma credencial temporária independente do SIP/SSO. A identidade
do ramal no canal SIP ainda não está vinculada criptograficamente à
sessão da API; o provisionamento e a entrega do token ao usuário
precisam ser feitos de maneira segura. O painel estático não armazena
o token e exige nova digitação ao abrir outra página.

As rotas legadas de métricas, SLA, relatórios, pausa, presença e outras
continuam com política própria ou legado e **não** estão abrangidas por
este isolamento. O tracker AMI e os redirecionamentos reais requerem
teste de concorrência e homologação em infraestrutura controlada.
A implantação deve permanecer bloqueada até auditoria do conjunto das
APIs e dos controles de produção.

PR em rascunho, sem merge ou implantação automáticos.
Marco 8 permanece aberto; progresso geral 7/16 (43,8%).
