# AXE PABX — 20 funcionalidades de análise operacional local

**Lote de desenvolvimento:** 30/10/2026. **Modalidade:** implementar código sem criar novos testes. Os gates obrigatórios já existentes no GitHub Actions permanecem habilitados. Nenhum teste na instalação local do usuário foi realizado nesta entrega.

## Funcionalidades implementadas em código

| # | Frente | Nova funcionalidade | Implementação |
| ---: | --- | --- | --- |
| 01 | Chamadas | Série diária de volume de chamadas por empresa | `call_volume_by_day` |
| 02 | Chamadas | Taxa de chamadas atendidas | `call_answer_rate` |
| 03 | Chamadas | Taxa de chamadas não atendidas | `call_missed_rate` |
| 04 | Chamadas | Total, média e mediana do tempo falado | `call_talk_time` |
| 05 | Chamadas | Identificação do dia de maior volume | `call_peak_day` |
| 06 | Satisfação | Média de satisfação da empresa | `survey_average_rating` |
| 07 | Satisfação | Distribuição de notas de 1 a 5 | `survey_rating_distribution` |
| 08 | Satisfação | Percentual de avaliações positivas | `survey_positive_rate` |
| 09 | Satisfação | Percentual de avaliações baixas | `survey_low_rating_rate` |
| 10 | Satisfação | Evolução diária da nota média | `survey_daily_average` |
| 11 | Agentes | Duração total das pausas encerradas | `pause_total_time` |
| 12 | Agentes | Pausas agrupadas por motivo | `pause_by_reason` |
| 13 | Agentes | Pausas agrupadas por ramal | `pause_by_agent` |
| 14 | Agentes | Identificação da pausa mais longa encerrada | `pause_longest` |
| 15 | Agentes | Histórico diário de segundos em pausa | `pause_daily_trend` |
| 16 | Campanhas | Distribuição de status dos contatos | `campaign_status_breakdown` |
| 17 | Campanhas | Percentual de contatos finalizados | `campaign_completion_rate` |
| 18 | Campanhas | Quantidade de primeiras tentativas, rediscagens e esgotados | `campaign_retry_pool` |
| 19 | Campanhas | Volume e média de tentativas por contato | `campaign_attempts_summary` |
| 20 | Campanhas | Volume de contatos e tentativas por operador | `campaign_agent_workload` |

## Como acessar localmente

As vinte funcionalidades ficam disponíveis por quatro comandos somente leitura, cada um devolvendo cinco resultados. Para preservar a segregação, **é obrigatório informar uma empresa específica** (`t1`, `t2` etc.). Nunca usar um prefixo parcial para selecionar `t1` e `t10`.

Após instalar o serviço `queue-api` em uma máquina autorizada, executar em um terminal local:

```bash
docker exec pabx-queue-api python3 /app/insights_cli.py --area calls --tenant t1 --file /app/data/call_log.jsonl
docker exec pabx-queue-api python3 /app/insights_cli.py --area survey --tenant t1 --file /app/data/survey.jsonl
docker exec pabx-queue-api python3 /app/insights_cli.py --area pauses --tenant t1 --file /app/data/pause_history.jsonl
docker exec pabx-queue-api python3 /app/insights_cli.py --area campaigns --tenant t1 --file /app/data/campaigns.json
```

Os arquivos são os caminhos configurados no `docker-compose.yml`; a operação exige que o serviço e os respectivos arquivos já existam. Se não existirem, o comando falha sem criar nem modificar dados. É possível executar também no checkout Python, usando caminhos locais de arquivos equivalentes.

## Limitações e cuidados

- **Sem novas rotas HTTP, sem mudança em Asterisk e sem disparar campanhas.** São novas funcionalidades de relatório **no backend e CLI local**, não painéis na interface do usuário.
- Não há controle de login/role na CLI: executar somente em host protegido, com acesso local concedido a um operador autorizado. Não expor este comando publicamente ou a usuários sem permissão.
- Não imprime identificadores de clientes, áudios, números discados, tokens ou linhas brutas; os resultados contêm apenas contagens, durações, datas e ramais de agentes pertencentes ao tenant selecionado.
- Os relatórios de chamadas só consideram registros do `CallLogStore`; a taxa de não atendidas **não** deve ser tratada como taxa de abandono em fila.
- As pausas informam exclusivamente sessões encerradas, nunca inventam duração de pausas abertas.
- As campanhas com tenant ausente ou ramal incompatível são descartadas (falha fechada), e nenhuma rediscagem é iniciada pelo relatório.
- A IA, SSO e integração de gravações permanecem com seus escopos anteriores; este lote não resolve essas pendências.
- **Status de cada item:** `CODE_REGISTERED_PENDING_REAL_HOMOLOGATION`. Não marcar em produção ou homologado sem execução no ambiente-alvo.
- O percentual global formal **não é atualizado** por adicionar relatórios: permanece baseado nos critérios de aceite do programa.

Arquivos: `queue-api/insights_common.py`, `insights_calls.py`, `insights_survey.py`, `insights_pauses.py`, `insights_campaigns.py` e `insights_cli.py`.
