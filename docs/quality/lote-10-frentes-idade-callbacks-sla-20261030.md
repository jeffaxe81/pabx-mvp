# AXE PABX — dez frentes adicionais: pendências de callback e capacidade/SLA

Data de registro: **30/10/2026**. Base técnica: entrega anterior de callbacks e CDR não atendidos (PR #179). Esta entrega foi reconstruída diretamente sobre a `main`, após merge por squash da PR #179; substitui a PR #180, que apresentou conflito de histórico. **Status:** `CODE_REGISTERED_PENDING_REAL_HOMOLOGATION`.

O lote adiciona **10 indicadores locais** (cinco por área) à CLI existente: de **70 para 80 funções de análise**, divididas em 16 áreas. As dez frentes não representam dez módulos de telefonia completos, nem dez integrações externas, nem dez desenvolvedores autônomos.

## Escopo entregue em código

| Frente | Área | Função | Objetivo |
|---:|---|---|---|
| 01 | callback_aging | `callback_oldest_pending_seconds` | Idade do callback pendente mais antigo |
| 02 | callback_aging | `callback_median_pending_seconds` | Mediana da idade dos pendentes |
| 03 | callback_aging | `callback_pending_age_bands` | Pendentes por faixas de 5m, 30m e 2h |
| 04 | callback_aging | `callback_pending_over_one_hour` | Quantidade e percentual aguardando há pelo menos 1h |
| 05 | callback_aging | `callback_pending_created_weekday` | Pedidos ainda pendentes agrupados pelo dia de criação UTC |
| 06 | sla_capacity | `sla_out_of_target_by_queue` | Chamadas fora do SLA por fila |
| 07 | sla_capacity | `sla_monthly_weighted_rate` | SLA mensal ponderado pelo volume |
| 08 | sla_capacity | `sla_most_loaded_queue` | Fila de maior volume oferecido |
| 09 | sla_capacity | `sla_weekday_weighted_rate` | SLA por dia da semana, ponderado |
| 10 | sla_capacity | `sla_latest_recorded_day` | Dia mais recente disponível no histórico válido |

## Como consultar, somente em host local autorizado

```bash
docker exec pabx-queue-api python3 /app/insights_cli.py --area callback_aging --tenant t1 --file /app/data/callbacks.json
docker exec pabx-queue-api python3 /app/insights_cli.py --area sla_capacity --tenant t1 --file /app/data/sla_history.jsonl
```

A CLI exige **tenant canônico exato** (por exemplo `t1`) e não combina `t1` com `t10`. Arquivos locais têm limites de tamanho, não são expostos em novas APIs e os resultados não incluem telefones, nomes, CallerID, gravações nem IDs de pedidos. IDs de callbacks vazios/repetidos rejeitam o catálogo completo. Cálculos de idade ignoram pedidos com data futura; não é feita tentativa de discagem nem chamada ao Asterisk.

Dados de idade dependem do relógio do host no instante da consulta. A área `sla_capacity` usa o histórico de filas com `offered`/`within_sla` válidos, recalculando os percentuais. "Fora do SLA" é `offered - within_sla`: não significa abandono de fila. Resultado vazio não é evidência de ausência de tráfego e `sla_latest_recorded_day` não comprova atualização em tempo real.

## Critérios de integração e limites de homologação

- Não foram escritos novos testes e não foi executado ambiente operacional real neste lote. CI já existente **continua obrigatória** para eventual merge.
- A PR parte da `main` já contendo a #179. A integração exige CI completamente aprovada no SHA final e ausência de conflitos.
- Não altera Asterisk, dialplan, serviços, políticas de gravação, autenticação HTTP ou arquivos de produção.
- `docs/plano-16-semanas-pabx.json` e `docs/quality/provas-operacionais-diferidas.json` ficam intocados. **7/16 marcos = 43,8%**; 15 provas operacionais continuam pendentes.
- **Produção NO-GO**, com `operational_go_authorized=false` e aceite humano ainda exigido.

Arquivos entregues: `queue-api/insights_callback_aging.py`, `queue-api/insights_sla_capacity.py` e atualização de `queue-api/insights_cli.py`.
