# AXE PABX — 20 frentes locais adicionais de operação e auditoria (30/10/2026)

**Escopo realizado:** funções Python + CLI para leitura local. **Não são novas APIs HTTP, softphone, interface de supervisão, automação de chamadas nem funcionalidades prontas para produção.** O objetivo é disponibilizar diagnósticos por empresa de arquivos já gerados pelo PABX e de exportações RTCP autorizadas.

A versão anterior continha 90 funções em 18 áreas. Este lote acrescenta **20 funções e quatro áreas** (`quality_advanced`, `cdr_integrity`, `callback_health` e `sla_risk`), resultando em **110 indicadores locais em 22 áreas**, após merge e CI integralmente verde.

## Frentes implementadas

| Nº | Área | Função | Finalidade |
|---:|---|---|---|
| 91 | qualidade RTCP | `quality_p95_jitter` | Jitter p95 das amostras válidas |
| 92 | qualidade RTCP | `quality_p95_rtt` | RTT p95 das amostras válidas |
| 93 | qualidade RTCP | `quality_high_loss_rate` | Taxa de perda maior que 3% |
| 94 | qualidade RTCP | `quality_metric_coverage` | Cobertura de jitter/perda/RTT |
| 95 | qualidade RTCP | `quality_worst_agent_sample_rate` | Ramal com maior proporção de amostras ruins, mínimo três |
| 96 | auditoria CDR | `cdr_unknown_status_by_day` | Disposições desconhecidas por dia válido |
| 97 | auditoria CDR | `cdr_answered_zero_duration` | ANSWERED com zero segundos faturáveis |
| 98 | auditoria CDR | `cdr_nonanswered_with_billable` | Não atendidas com faturamento informado |
| 99 | auditoria CDR | `cdr_answered_missing_operator_rate` | Taxa ANSWERED sem ramal atribuível |
| 100 | auditoria CDR | `cdr_invalid_disposition_structure` | Campos de disposição estruturalmente inválidos |
| 101 | saúde de callbacks | `callback_pending_over_24h` | Pendentes há pelo menos 24h |
| 102 | saúde de callbacks | `callback_pending_over_48h` | Pendentes há pelo menos 48h |
| 103 | saúde de callbacks | `callback_pending_exhausted_attempts` | Pendentes com máximo de tentativas |
| 104 | saúde de callbacks | `callback_completed_by_attempts` | Concluídos por tentativa registrada |
| 105 | saúde de callbacks | `callback_pending_share` | Participação de pendentes no catálogo |
| 106 | risco de SLA | `sla_consecutive_days_below_eighty` | Maior sequência diária contínua abaixo de 80% |
| 107 | risco de SLA | `sla_monthly_outside_target_count` | Contagem fora do SLA por mês |
| 108 | risco de SLA | `sla_queue_traffic_share` | Participação percentual de volume de cada fila |
| 109 | risco de SLA | `sla_lowest_rate_queue_min_ten` | Fila com menor SLA com amostra mínima de 10 chamadas |
| 110 | risco de SLA | `sla_best_day` | Dia de melhor SLA ponderado no arquivo |

## Exemplos locais (somente onde arquivos já existam)

```bash
python3 queue-api/insights_cli.py --area quality_advanced --tenant t1 --file /tmp/quality_export.json
python3 queue-api/insights_cli.py --area cdr_integrity --tenant t1 --file /tmp/call_log.jsonl
python3 queue-api/insights_cli.py --area callback_health --tenant t1 --file /tmp/callbacks.json
python3 queue-api/insights_cli.py --area sla_risk --tenant t1 --file /tmp/sla_history.jsonl
```

Esses caminhos são **exemplos**. O arquivo precisa existir em um host autorizado; o CLI não exporta dados nem interage com Asterisk. Entradas JSONL ou JSON-array têm limites de tamanho, tipo e quantidade, e cada área usa exatamente seu formato esperado.

## Limites explícitos de interpretação e segurança

- Tenant identificado por igualdade exata, sem misturar `t1` e `t10`. Nenhuma saída contém telefone, CallerID, gravação, nota de presença, nomes de clientes ou URI de mídia.
- **RTCP:** as funções consideram somente amostras válidas do export local; ausência de amostra não equivale a qualidade excelente; limiares 30 ms e 3% são referências de diagnóstico, não SLA contratual; o agregado por ramal não é avaliação de pessoa.
- **CDR:** resultados de Disposition não são sinônimo de chamadas abandonadas em fila; inconsistências de faturamento são sinais de auditoria, não cobrança comprovadamente incorreta; o operador do CDR é uma associação técnica.
- **Callbacks:** a função valida a unicidade global dos IDs do catálogo; idades usam relógio local e ignoram timestamp futuro; não há agenda automática, tentativa de chamada, mudança de status ou autorização de contato.
- **SLA:** utiliza contadores `offered` e `within_sla` válidos por fila `fila-tN...`; percentuais são ponderados por volume. O limiar de **80% é ilustrativo**, não contratual; data ausente não é tratada como zero.
- A CLI **não implementa autenticação nem autorização HTTP**. Os arquivos de origem devem estar protegidos e a execução restrita a administradores autorizados.
- Nenhum teste novo foi acrescentado, mas a **CI existente é gate obrigatório**. Nenhuma execução em ambiente real de cliente é afirmada neste lote. Sem mudança em dialplan, PJSIP, banco de clientes, autenticação, gravação ou deploy.
- Marcos formais continuam **7/16 (43,8%)**, com **15 evidências reais pendentes** (issue #173). `operational_go_authorized=false`; **produção NO-GO**.

**Status do lote:** `CODE_REGISTERED_PENDING_REAL_HOMOLOGATION`. Merge apenas após todos os checks da PR aprovados.

**Arquivos:** `queue-api/insights_quality_advanced.py`, `queue-api/insights_cdr_integrity.py`, `queue-api/insights_callback_health.py`, `queue-api/insights_sla_risk.py`, `queue-api/insights_cli.py`.
