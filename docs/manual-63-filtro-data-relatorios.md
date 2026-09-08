# Manual 63 — Filtro de intervalo de datas nos relatórios (item #63)

## O que fecha
Duas limitações documentadas, ambas da mesma natureza, fechadas de
uma vez com uma abordagem consistente:
- Manual 57 (histórico de pausa): **"sem filtro por período"**
- Manual 59 (histórico de SLA): **"sem filtro de intervalo de datas
  na interface"**

## Como funciona
Os dois relatórios (`GET /api/reports/pauses` e
`GET /api/metrics/sla/history`) agora aceitam `?start=AAAA-MM-DD` e
`?end=AAAA-MM-DD` (os dois opcionais, e inclusivos — o dia informado
em `start`/`end` entra no resultado, não é excluído). Sem nenhum dos
dois, devolve tudo, exatamente como antes.

```
GET /api/reports/pauses?start=2026-01-01&end=2026-01-31
GET /api/metrics/sla/history?start=2026-01-15
```

## Uma diferença sutil entre os dois filtros
O histórico de SLA já guarda a data como string pronta
(`{"date": "2026-01-15", ...}`) — filtrar é só comparação de string.
O histórico de pausa guarda **timestamps** (`started_at`, quando a
pausa começou), não uma data formatada — o filtro precisa converter
o timestamp pra data local antes de comparar
(`filter_pause_records_by_date_range`). Usa `started_at`, não
`ended_at`: uma pausa que começou às 23h50 e terminou depois da meia-
noite pertence ao dia em que **começou**, não ao dia seguinte.

## Interface no painel operacional
As duas seções (histórico de pausa e histórico de SLA) ganharam
campos "De"/"Até" e botões "Filtrar"/"Limpar". O filtro escolhido é
guardado numa variável **fora** de `fetchAll()` — sem isso, o
próximo ciclo automático de atualização do painel (a cada poucos
segundos) apagaria o filtro escolhido, voltando a mostrar tudo.

## Como testar manualmente
1. `docker compose up -d`, gere histórico de pausa/SLA de alguns dias
   diferentes (ou ajuste o relógio do sistema pra simular)
2. No painel operacional, filtre por um intervalo de datas específico
   em cada seção — confirme que só os dias dentro do intervalo
   aparecem
3. Clique "Limpar" — confirme que volta a mostrar tudo
4. Espere um ciclo de atualização automática acontecer com o filtro
   ativo — confirme que o filtro continua aplicado (não volta a
   mostrar tudo sozinho)

## Teste automatizado
- `queue-api/tests/test_agent_pause.py` (5 testes novos) —
  `filter_pause_records_by_date_range`: limites inclusivos, sem
  limites devolve tudo, só início, só fim, lista vazia
- `queue-api/tests/test_queue_sla.py` (5 testes novos) — mesma
  cobertura pra `filter_sla_history_by_date_range`
- `queue-api/tests/test_server_routes.py` (2 testes novos) — os dois
  endpoints aplicam o filtro antes de resumir
- `tests/test_ops_panel.py` (4 testes novos) — filtro sobrevive ao
  polling automático, as duas buscas incluem os parâmetros de query,
  botões "Limpar" resetam e buscam de novo
- **909 testes no total**, em 8 suítes

## Estado do projeto depois deste item
Com isso, as duas últimas lacunas documentadas nos manuais anteriores
(57, 59) estão fechadas. Não há, no momento desta escrita, nenhuma
limitação funcional conhecida pendente nos itens já implementados —
o que resta são os limites estruturais já aceitos desde o início do
projeto (nunca testado contra um Asterisk real, IA local nunca
validada com hardware de verdade, sem alta disponibilidade de fato),
não lacunas de funcionalidade.

## Limitações conhecidas (honestidade técnica)
- **Sem validação de formato de data** — se `start`/`end` vierem num
  formato diferente de `AAAA-MM-DD`, a comparação de string
  simplesmente não vai bater com nada corretamente (silenciosamente
  devolve resultado vazio ou incorreto, não um erro `400` explícito)
- **Sem atalhos de período** ("hoje", "esta semana", "este mês") —
  só o campo de data bruto, o usuário escolhe manualmente
- **Nunca testado contra um Asterisk real** — mesma situação de
  sempre pro resto das integrações deste projeto
