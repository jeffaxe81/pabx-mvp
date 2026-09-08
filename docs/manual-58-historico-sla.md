# Manual 58 — Histórico de SLA por dia (item #58)

## O que fecha
O manual 46 (SLA de fila) documentou explicitamente como limitação:
**"sem histórico — o snapshot() é sempre do dia atual"**. Este item
fecha essa lacuna.

## Como funciona
O `QueueSLATracker` (manual 46) já resetava à meia-noite — agora,
**antes** de resetar, persiste o resumo completo do dia que está
terminando (por fila) num arquivo JSONL, mesmo padrão já usado no
histórico de pausa (manual 57) e em `survey.py`/`reports.py`.

```
Meia-noite vira o dia → ANTES de zerar os contadores:
                           grava {data, fila, offered, within_sla, sla_percent}
                           pra cada fila que teve chamada oferecida
                         → só então zera pra começar o dia novo
```

## Onde aparece
**`GET /api/metrics/sla/history`** — `{"by_date": {"2026-01-15": {"fila-t1": {"offered": 40, "within_sla": 32, "sla_percent": 80.0}}, "2026-01-16": {...}}}`

Agrupado por data e depois por fila, pra dar pra comparar visualmente
dia a dia sem precisar processar o array bruto na mão.

## Uma armadilha de rota evitada
`/api/metrics/sla/history` **começa com** `/api/metrics/sla` — se a
checagem da rota genérica (dia atual) viesse primeiro no `do_GET`, o
`startswith()` faria a rota de histórico cair por engano na de hoje,
e o endpoint de histórico nunca seria alcançado. A checagem mais
específica precisa vir **antes**. Isso é testado explicitamente
(`test_sla_history_route_checked_before_generic_sla_route`).

## Fila sem chamada não polui o histórico
Se uma fila não recebeu nenhuma chamada no dia (`offered == 0`), ela
não gera registro nenhum no histórico — um "0% de SLA" pra uma fila
que simplesmente não tocou seria enganoso, não uma métrica real.

## Como testar manualmente
Como o reset só acontece à meia-noite de verdade, testar isso
manualmente exigiria esperar a virada do dia — o teste automatizado
(com relógio injetável) é o caminho prático pra validar o
comportamento sem precisar disso. Pra conferir manualmente depois de
alguns dias de uso real:
1. `docker compose up -d`, deixe rodando por mais de um dia com
   chamadas de verdade
2. Consulte `GET /api/metrics/sla/history` — confirme que aparece um
   registro por dia/fila que teve chamada

## Teste automatizado
- `queue-api/tests/test_queue_sla.py` (10 testes novos) — reset à
  meia-noite persiste o resumo do dia anterior, primeiro dia nunca
  persiste nada (não há "ontem"), fila sem chamada não gera registro
  vazio, `QueueSLATracker` continua funcionando sem `history_store`
  (opcional), `SLAHistoryStore` (append/load, arquivo ausente, linha
  corrompida ignorada), `summarize_sla_history_by_date`
- `queue-api/tests/test_server_routes.py` (3 testes novos) — ordem
  de checagem de rota correta, endpoint usa o histórico persistido
- `tests/test_docker_compose.py::test_sla_history_path_configured_for_queue_api`
- **876 testes no total**, em 8 suítes

## Limitações conhecidas (honestidade técnica)
- **Sem interface no painel ainda** — só a API expõe o histórico;
  o painel operacional (manual 46) continua mostrando só o dia atual
- **Sem filtro de intervalo de datas** — a resposta sempre traz o
  histórico completo acumulado desde o início; consultar só "última
  semana" exigiria filtrar do lado de quem consome a API
- **Nunca testado esperando uma virada de dia real** — só com relógio
  injetável (mesma limitação, aliás, do reset diário do manual 46
  desde o início)
