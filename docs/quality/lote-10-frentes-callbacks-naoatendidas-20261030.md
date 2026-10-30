# AXE PABX — lote de 10 frentes: callbacks e chamadas não atendidas

**Registro:** 30/10/2026. **Entrega:** código em branch de desenvolvimento, não homologação operacional. **Status:** `CODE_REGISTERED_PENDING_REAL_HOMOLOGATION`. Este lote passa de **60 para 70 indicadores de análise local** (14 áreas com 5 indicadores). Não corresponde a dez módulos de produção independentes, telas ou operadores paralelos.

## Frentes implementadas

| Frente | Área | Função | Resultado |
|---:|---|---|---|
| 01 | Callback | `callback_status_counts` | Total por estado conhecido |
| 02 | Callback | `callback_completion_rate` | Conclusão entre pedidos com estado terminal |
| 03 | Callback | `callback_attempt_distribution` | Distribuição de 0 a 2 tentativas |
| 04 | Callback | `callback_pending_per_day` | Pendentes por data UTC de abertura |
| 05 | Callback | `callback_pending_retry_pool` | Primeiro contato, nova tentativa e revisão manual |
| 06 | Chamadas não atendidas | `unanswered_reason_counts` | Disposition reconhecida para não atendidas |
| 07 | Chamadas não atendidas | `unanswered_daily_volume` | Quantidade diária |
| 08 | Chamadas não atendidas | `unanswered_by_agent` | Volume por ramal válido associado |
| 09 | Chamadas não atendidas | `unanswered_monthly_volume` | Tendência mensal |
| 10 | Chamadas não atendidas | `unanswered_daily_rate` | Percentual por dia entre CDRs conhecidos |

## Execução local autorizada

No container da queue-api, usando arquivos já existentes e sem criar novos dados:

```bash
docker exec pabx-queue-api python3 /app/insights_cli.py --area callbacks --tenant t1 --file /app/data/callbacks.json
docker exec pabx-queue-api python3 /app/insights_cli.py --area unanswered --tenant t1 --file /app/data/call_log.jsonl
```

A área `callbacks` lê um **array JSON** do snapshot `callbacks.json`; `unanswered` lê o **JSONL de CDR** existente. Nenhum acesso remoto, endpoint público ou ação sobre clientes é implementado. O arquivo de callbacks com IDs vazios ou repetidos gera erro, inclusive se houver ambiguidade entre empresas. Dados de `t10` não aparecem em relatório de `t1`; registros legados sem tenant não são inferidos nem incluídos. Dados pessoais (nomes, telefones, gravações e identificadores de pedido) não aparecem nas saídas.

**Limitações semânticas:** `unanswered` contabiliza CDRs com disposições conhecidas diferentes de `ANSWERED`. Um CDR não atendido não é sinônimo de abandono real de fila. As contagens por operador indicam associação no CDR e não atribuição de culpa. `callback_completion_rate` usa como denominador apenas pedidos `concluido`, `cancelado` ou `esgotado`. `callback_pending_retry_pool` é observacional e não agenda novas discagens.

## Segurança, aceitação e gate

- A CLI é somente leitura, sem RBAC próprio. Executar apenas no host por pessoa autorizada e sem publicar seus arquivos via rede.
- Não foram incluídos testes novos nem solicitadas provas operacionais; verificações preexistentes da CI continuam condicionando eventual merge.
- **Não existe execução comprovada no ambiente-alvo**. Há 15 provas operacionais diferidas, descritas em `docs/quality/provas-operacionais-diferidas.json` e na issue #173.
- Marcos formais permanecem **7/16 = 43,8%**; Marco 8 e seguintes não são automaticamente concluídos por mais código.
- `operational_go_authorized=false`. Nenhum deploy ou liberação produtiva integra esta alteração.

**Arquivos:** `queue-api/insights_callbacks.py`, `queue-api/insights_unanswered.py`, integração em `queue-api/insights_cli.py`.
