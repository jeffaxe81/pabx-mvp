# Manual 142 — Membros dinâmicos de fila (Call Center de voz)

## 10 capacidades no primeiro lote
1. Login dinâmico de membro em fila (QueueAdd)
2. Logout dinâmico de membro de fila (QueueRemove)
3. Penalty de distribuição de 0 a 10 no login
4. Login inicialmente pausado
5. Pausa limitada a uma única fila (QueuePause)
6. Retomada limitada a uma única fila
7. Rastreamento de eventos de inclusão, remoção, pausa e status
8. Consulta autenticada dos membros observados, sem confundir t1 e t10
9. Autoatendimento limitado ao próprio ramal e gestão do supervisor do tenant
10. Interface web responsiva para consulta e operações

## Endpoints
- GET /api/queue/members — devolve apenas o tenant da credencial, nunca da query.
- POST /api/queue/members/join — queue, extension, penalty (0..10), paused (booleano).
- POST /api/queue/members/leave — queue e extension.
- POST /api/queue/members/pause — queue, extension, paused, reason (obrigatório ao pausar).

## Segurança e habilitação
Exige Bearer do catálogo privado de filas e CORS exato. O agente pode alterar apenas o próprio ramal. Supervisor/admin podem alterar membros autorizados do seu tenant. Nomes de fila permitidos: fila-tN, fila-tN-en e fila-tN-es. Só aceita ramais explicitamente autorizados em QUEUE_MEMBER_ALLOWED_EXTENSIONS.

QUEUE_MEMBER_MUTATIONS_ENABLED=false por padrão. Apenas após a homologação habilitar true.

AMI usa exclusivamente QueueAdd, QueueRemove e QueuePause com headers permitidos. Não aceita texto livre, Originate nem Command. O arquivo de catálogo de credenciais deve ser privado (0600).

## UI
Na interface web, acessar /agentes-filas.html ou o link do cockpit. Informar URL HTTPS da queue-api e o token; o navegador não grava token em localStorage, cookie nem query.

## Semântica do retorno e limitações
A resposta HTTP 202 confirma apenas ACK do comando AMI, NÃO a membresia efetiva. Estado somente muda após evento QueueMemberAdded, QueueMemberRemoved, QueueMemberPause ou QueueMemberStatus. O GET devolve complete_membership_inventory=false: o stream de eventos não prova o estado inicial nem cobre todos os membros estáticos existentes.

Membros estáticos em queues.conf podem não ser removíveis por QueueRemove. persistentmembers=yes pode preservar dinâmicos após reinício. Antes de ativar em produção, testar em Asterisk real login/logout, retomada, atendimento, múltiplos tenants, reload e recuperação de falha.

## Testes
- queue-api/tests/test_queue_membership.py — ações, tipos, ACL, penalty, pausa, tracker, isolamento e limites.
- queue-api/tests/test_queue_membership_http.py — HTTP real de loopback com AMI simulado, 401/403/415/502/503, CORS e isolamento.
- quality-gates.yml — pytest de queue-api.
- Gate pendente: validação operacional com Asterisk real e tráfego SIP, inclusive alterações de agentes durante chamadas.

São dez capacidades técnicas neste lote. Elas não representam conclusão integral do novo épico de 100 funcionalidades.