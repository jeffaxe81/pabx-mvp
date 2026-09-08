# Manual 46 — SLA de fila (item #46)

## O que é
Diferente do "tempo médio de espera" (métrica que já existia via
`metrics.py`), SLA é uma métrica **binária por chamada**: "foi
atendida dentro de N segundos? sim/não" — agregada como percentual.
É o indicador que qualquer contact center de verdade usa como meta
operacional (ex: "80% das chamadas atendidas em até 20 segundos").

**Este é o último item da auditoria** feita contra o framework de
avaliação de PABX corporativo fornecido pelo usuário (itens #40-46) —
fecha os sete gaps identificados naquela análise.

## Como funciona
Dois eventos AMI nativos do Asterisk alimentam o cálculo:
- **`AgentConnect`** — chamada foi atendida; o campo `HoldTime` já
  vem calculado pelo próprio Asterisk (segundos que esperou na fila)
- **`QueueCallerAbandon`** — cliente desistiu antes de ser atendido;
  conta **contra** o SLA (nunca foi atendida de fato), mas ainda faz
  parte do total de chamadas oferecidas à fila

```
SLA% = (chamadas atendidas dentro do limiar) / (total oferecido) × 100
```

Uma chamada abandonada com espera curta (ex: cliente desligou em 5s)
**não conta como "dentro do SLA"**, mesmo que o tempo de espera seja
menor que o limiar — ela nunca foi atendida, então não pode contar a
favor. Esse foi, aliás, um bug real que os próprios testes
automatizados pegaram durante a implementação (ver seção de testes).

## Configuração
Variável de ambiente do `queue-api`:
```
SLA_THRESHOLD_SECONDS=20
```
20 segundos é uma referência comum de mercado, não uma regra fixa —
ajuste conforme a meta real da operação.

## Onde aparece
- **`GET /api/metrics/sla`** — `{"threshold_seconds": 20, "queues": {"fila-t1": {"offered": 40, "within_sla": 32, "sla_percent": 80.0}, ...}}`
- **Painel operacional** — seção "SLA de fila", uma linha por fila,
  com percentual, limiar e os números absolutos (nunca só o
  percentual sozinho, que perderia contexto)

## Reset diário
Mesmo padrão de `metrics.py` (`DailyMetrics`) — o contador reinicia à
meia-noite, com relógio injetável pros testes não dependerem de
esperar a virada do dia de verdade.

## Como testar manualmente
1. `docker compose up -d`
2. Faça algumas chamadas pra fila, atendendo algumas rápido e
   deixando outras esperarem mais que 20s antes de atender
3. Abandone uma chamada de propósito (ligue, desligue antes de
   alguém atender)
4. Consulte `GET /api/metrics/sla` ou veja o painel operacional —
   confirme que o percentual reflete corretamente as chamadas
   atendidas a tempo vs. as demoradas/abandonadas

## Teste automatizado
- `queue-api/tests/test_queue_sla.py` (14 testes) — parsing dos dois
  eventos, chamada dentro/fora do limiar, **abandono conta contra o
  SLA mesmo com espera curta** (o bug real encontrado e corrigido
  durante a implementação), cálculo correto com múltiplas chamadas,
  filas rastreadas independentemente, limite exatamente no valor do
  limiar conta como dentro, reset à meia-noite
- `queue-api/tests/test_server_routes.py` — endpoint expõe limiar e
  detalhamento por fila, eventos `AgentConnect`/`QueueCallerAbandon`
  alimentam o rastreador
- `tests/test_ops_panel.py` — painel busca e renderiza o SLA, mostra
  percentual+limiar+números absolutos juntos, trata fila vazia sem
  quebrar

## Bug real encontrado e corrigido durante este trabalho
A primeira versão do `_record()` calculava "dentro do SLA" só
olhando pro `hold_time`, sem considerar se a chamada foi de fato
**atendida** ou **abandonada**. Isso significava que uma chamada
abandonada com espera curta (ex: 5 segundos) contava incorretamente
como "dentro do SLA" — um bug que inflaria artificialmente a métrica
mais importante deste item. O teste
`test_abandoned_call_counts_against_sla` pegou isso antes de chegar a
qualquer lugar perto de produção.

## Limitações conhecidas (honestidade técnica)
- **Limiar único e global** — não é configurável por fila
  individualmente (a fila de vendas e a de suporte usam o mesmo
  `SLA_THRESHOLD_SECONDS`)
- **Sem histórico** — o `snapshot()` é sempre do dia atual; pra
  comparar SLA de hoje com o de ontem/semana passada, seria preciso
  persistir o histórico diário (natural extensão futura,
  reaproveitando o padrão JSONL já usado em `reports.py`)
- **Sem alerta automático** quando o SLA cai abaixo da meta — a
  interface só mostra a cor (verde/amarelo) quando alguém está
  olhando o painel, não dispara notificação proativa
- **Sem teste de integração real** contra o Asterisk de verdade —
  mesma situação já documentada pro resto das integrações AMI do
  projeto
