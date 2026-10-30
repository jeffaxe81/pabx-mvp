# AXE PABX — 40 novos indicadores locais (lote 30/10/2026)

**Modalidade:** 40 funções de código em oito novas áreas. Sem escrever novas suítes de teste; manter obrigatoriamente a CI já configurada no GitHub, inclusive laboratório descartável Asterisk. Não executar telefonia, clientes ou ambiente local real. Todos os recursos permanecem `CODE_REGISTERED_PENDING_REAL_HOMOLOGATION`.

Este lote estende as 20 análises anteriores da `queue-api/insights_cli.py` para **60 indicadores em 12 áreas de cinco funções**. É um conjunto de relatórios locais somente leitura — **não são 40 telas, endpoints ou módulos de voz novos**.

## Funcionalidades criadas

| Nº | Área | Funcionalidade nova | Função |
|---:|---|---|---|
| 21 | calls_advanced | Chamadas por resultado/disposition | `calls_disposition_breakdown` |
| 22 | calls_advanced | Volume por atendente | `calls_volume_by_agent` |
| 23 | calls_advanced | Atendidas por atendente | `calls_answered_by_agent` |
| 24 | calls_advanced | Tempo falado por atendente | `calls_talk_time_by_agent` |
| 25 | calls_advanced | Distribuição por duração da chamada | `calls_duration_bands` |
| 26 | calls_trends | Chamadas por dia da semana | `calls_weekday_volume` |
| 27 | calls_trends | Chamadas por semana ISO | `calls_weekly_volume` |
| 28 | calls_trends | Chamadas por mês | `calls_monthly_volume` |
| 29 | calls_trends | Taxa mensal de atendimento | `calls_monthly_answer_rate` |
| 30 | calls_trends | Taxa diária de atendimento | `calls_daily_answer_rate` |
| 31 | calls_audit | Contagem de datas inválidas no histórico | `calls_invalid_date_count` |
| 32 | calls_audit | Atendidas sem duração válida | `calls_missing_answered_duration` |
| 33 | calls_audit | Resultados CDR fora da lista conhecida | `calls_unknown_disposition_count` |
| 34 | calls_audit | Atendidas sem operador atribuível | `calls_missing_operator_count` |
| 35 | calls_audit | Duração inconsistente ou inválida | `calls_negative_duration_conflicts` |
| 36 | survey_advanced | Mediana de satisfação | `survey_median_score` |
| 37 | survey_advanced | Notas por atendente | `survey_score_by_agent` |
| 38 | survey_advanced | Taxa de notas neutras | `survey_neutral_rate` |
| 39 | survey_advanced | Respostas por semana | `survey_weekly_response_count` |
| 40 | survey_advanced | Média mensal de satisfação | `survey_monthly_average` |
| 41 | pauses_advanced | Duração média das pausas | `pause_average_duration` |
| 42 | pauses_advanced | Mediana das pausas | `pause_median_duration` |
| 43 | pauses_advanced | Pausas por faixa de duração | `pause_duration_bands` |
| 44 | pauses_advanced | Segundos em pausa por dia da semana | `pause_weekday_seconds` |
| 45 | pauses_advanced | Quantidade de agentes com pausa encerrada | `pause_active_agent_count` |
| 46 | campaigns_advanced | Percentual de contatos atendidos | `campaigns_answered_share` |
| 47 | campaigns_advanced | Percentual de contatos ocupados | `campaigns_busy_share` |
| 48 | campaigns_advanced | Percentual sem resposta | `campaigns_no_answer_share` |
| 49 | campaigns_advanced | Quantos contatos estão no estado discando | `campaigns_in_progress_count` |
| 50 | campaigns_advanced | Atendidas por operador da campanha | `campaigns_answered_by_agent` |
| 51 | sla_history | SLA geral ponderado por volume | `sla_weighted_rate` |
| 52 | sla_history | Chamadas oferecidas por dia | `sla_offered_by_day` |
| 53 | sla_history | SLA por fila | `sla_rate_by_queue` |
| 54 | sla_history | Dias abaixo de 80% de SLA | `sla_days_below_eighty` |
| 55 | sla_history | Dia de pior SLA | `sla_worst_day` |
| 56 | quality_export | Jitter médio medido | `quality_average_jitter` |
| 57 | quality_export | Taxa de amostras com jitter acima de 30 ms | `quality_jitter_high_rate` |
| 58 | quality_export | Perda de pacotes média medida | `quality_average_packet_loss` |
| 59 | quality_export | RTT médio medido | `quality_average_rtt` |
| 60 | quality_export | Amostras de pior qualidade por agente | `quality_poor_by_agent` |

## Uso local, mediante acesso autorizado

Os grupos `calls_advanced`, `calls_trends` e `calls_audit` leem o arquivo de chamadas existente `/app/data/call_log.jsonl`. O grupo `survey_advanced` lê `/app/data/survey.jsonl`; `pauses_advanced`, `/app/data/pause_history.jsonl`; `campaigns_advanced`, `/app/data/campaigns.json`; e `sla_history`, `/app/data/sla_history.jsonl`.

Exemplos:

```bash
docker exec pabx-queue-api python3 /app/insights_cli.py --area calls_advanced --tenant t1 --file /app/data/call_log.jsonl
docker exec pabx-queue-api python3 /app/insights_cli.py --area calls_trends --tenant t1 --file /app/data/call_log.jsonl
docker exec pabx-queue-api python3 /app/insights_cli.py --area calls_audit --tenant t1 --file /app/data/call_log.jsonl
docker exec pabx-queue-api python3 /app/insights_cli.py --area survey_advanced --tenant t1 --file /app/data/survey.jsonl
docker exec pabx-queue-api python3 /app/insights_cli.py --area pauses_advanced --tenant t1 --file /app/data/pause_history.jsonl
docker exec pabx-queue-api python3 /app/insights_cli.py --area campaigns_advanced --tenant t1 --file /app/data/campaigns.json
docker exec pabx-queue-api python3 /app/insights_cli.py --area sla_history --tenant t1 --file /app/data/sla_history.jsonl
```

`quality_export` depende de um **JSON array produzido por exportação local autorizada** de entradas do `QualityLog` (campos `channel`, `jitter_ms`, `packet_loss_percent`, `rtt_ms`). O `QualityLog` atual é mantido **em memória**, não em arquivo persistido pela aplicação; esta entrega **não** criou captura ou exportação automática. Um operador pode preparar um arquivo `/app/data/quality_export.json` privado e executar:

```bash
docker exec pabx-queue-api python3 /app/insights_cli.py --area quality_export --tenant t1 --file /app/data/quality_export.json
```

Se o arquivo de entrada não existir, a CLI não inventa resultados e falha sem modificar dados. `quality_export` calcula a taxa de baixa qualidade apenas das amostras com jitter/perda disponíveis; dados faltantes não equivalem a "boa qualidade".

## Segurança e limites

- Todas as consultas são **somente leitura** e exigem empresa `tN` exata. As filas são identificadas por `fila-tN` ou `fila-tN-sufixo`. `t1` não contém `t10`.
- Não imprime números telefônicos de clientes, mensagens, gravações, tokens ou eventos AMI brutos. Pode incluir nomes técnicos de ramal, data, contagem e tempo.
- A CLI não autentica usuários nem aplica permissões de acesso a arquivos: **executar somente em host local autorizado** e não expor via rede ou dar acesso a pessoa não autorizada.
- A filtragem de qualidade usa canais PJSIP associados ao tenant; **não** substitui autenticação/controle de acesso na origem do arquivo exportado.
- O SLA é refeito a partir de `offered`/`within_sla` por fila, desconsiderando o percentual armazenado. Registros inconsistentes são ignorados; registros duplicados na origem devem ser corrigidos na coleta.
- Todos os 40 itens estão em **código**, não em telas do sistema. A execução no Windows/WSL2 e a aderência a dados reais ainda precisam de homologação.
- Não foram criados arquivos de teste novos, não houve deploy local, alteração de chamadas ou liberação de GO. A CI existente não representa comprovação no ambiente do usuário.
- A evolução formal de marcos no `docs/plano-16-semanas-pabx.json` e as 15 provas diferidas continuam inalteradas.

**Arquivos:** `queue-api/insights_calls_advanced.py`, `insights_calls_trends.py`, `insights_calls_audit.py`, `insights_survey_advanced.py`, `insights_pauses_advanced.py`, `insights_campaigns_advanced.py`, `insights_sla_history.py`, `insights_quality_export.py`, e atualização de `insights_cli.py`.
