# Manual 57 — Histórico de tempo em pausa por motivo (item #57)

## O que fecha
O manual 44 (motivo de pausa do agente) documentou explicitamente
como limitação: **"sem relatório histórico de tempo em pausa por
motivo — o estado é só o atual"**. Este item fecha essa lacuna.

## Como funciona
O `AgentPauseStore` (que já rastreava o estado *atual* de pausa via
evento `QueueMemberPause`, manual 44) agora também grava um registro
**completo** no momento em que o agente **despausa** — é o único
momento em que a duração real da pausa é conhecida por inteiro
(início + fim).

```
Agente pausa (Almoço) → guarda "desde quando" no estado atual
                              ↓ (algum tempo depois)
Agente despausa → calcula a duração completa → grava no histórico
                                                  (JSONL, mesmo padrão
                                                   de survey.py/reports.py)
```

## Honesto sobre o que não sabemos
Se o `queue-api` reiniciar **enquanto** um agente está pausado, o
primeiro evento de despausar que ele vir não tem um "pausou desde"
correspondente no estado atual (foi perdido no reinício). Nesse caso,
**nenhum registro é gravado** — a duração seria um chute, e um chute
apresentado como dado real seria pior que a lacuna. Isso é testado
explicitamente
(`test_unpause_without_prior_pause_state_does_not_crash_or_record`).

## Onde aparece
- **`GET /api/reports/pauses`** — `{"by_reason": {"Almoço": 3000.0, "Banheiro": 300.0}, "by_extension": {"t1-recepcao": {"total_seconds": 2100.0, "count": 2}}, "total_records": N}`
- **Painel operacional** — seção "Tempo em pausa por motivo", em
  minutos (mais legível que segundos crus pra acúmulos de horas de
  operação), ordenado do motivo com mais tempo acumulado pro com
  menos

## Como testar manualmente
1. `docker compose up -d`
2. Pause um ramal com motivo "Almoço", espere um pouco, despause
3. Repita com "Banheiro"
4. Consulte `GET /api/reports/pauses` ou veja o painel operacional —
   confirme que os dois motivos aparecem com o tempo certo

## Teste automatizado
- `queue-api/tests/test_agent_pause.py` (10 testes novos) —
  despausar grava histórico completo com duração correta, pausar
  sozinho não grava nada ainda, despausar sem pausa anterior
  conhecida não trava nem inventa dado, `AgentPauseStore` continua
  funcionando sem `history_store` (opcional), `PauseHistoryStore`
  (append/load, arquivo ausente, linha corrompida ignorada),
  `summarize_pause_time_by_reason`/`summarize_pause_time_by_extension`
- `queue-api/tests/test_server_routes.py::test_pause_history_report_exposes_totals_by_reason_and_extension`
- `tests/test_ops_panel.py` (3 testes novos) — buscado e renderizado,
  ordenado por tempo decrescente, trata estado vazio sem quebrar
- `tests/test_docker_compose.py::test_pause_history_path_configured_for_queue_api`
- **864 testes no total**, em 8 suítes

## Limitações conhecidas (honestidade técnica)
- **Sem filtro por período** (hoje/semana/mês) — o relatório sempre
  soma **todo** o histórico acumulado desde o início; comparar "esta
  semana vs. semana passada" exigiria filtrar por data, não
  implementado ainda
- **Pausas em andamento não entram no total** — só pausas já
  *completas* (despausadas) contam; se um agente está pausado agora
  há 2 horas, esse tempo não aparece até ele despausar
- **Sem exportação** (CSV/planilha) — só consulta via API/painel
- **Nunca testado contra um Asterisk real** — mesma situação de
  sempre pro resto das integrações AMI deste projeto
