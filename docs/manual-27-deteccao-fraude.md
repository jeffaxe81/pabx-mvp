# Manual 27 — Detecção de fraude (item #32)

## O que é
Três mecanismos de defesa contra o cenário clássico de fraude em PABX
(alguém invade e disca em massa pra números caros/internacionais até
a fatura explodir):

1. **Alerta de volume anormal** — mais de N chamadas externas pelo
   mesmo ramal numa janela curta de tempo
2. **Bloqueio automático de destino suspeito** — quando o volume
   anormal é detectado, o número pode ser bloqueado automaticamente
   (reaproveitando a mesma lista de bloqueio do manual 20)
3. **Limite de gasto diário por ramal** — alerta quando o custo
   estimado das chamadas de um ramal no dia passa de um limite
   configurado

## Como funciona
- **Volume anormal**: `CallRateTracker` (em memória) conta chamadas
  externas por ramal numa janela deslizante (padrão: 60 segundos,
  mais de 10 chamadas = anormal). É alimentado pelo evento AMI
  `DialBegin` sempre que uma chamada sai pelo tronco TDM
- **Bloqueio automático**: quando o volume é anormal E
  `FRAUD_AUTO_BLOCK=true`, o `queue-api` manda um `DBPut` na mesma
  família `blocklist` do AstDB que o dialplan já consulta (manual 20)
  — o número fica bloqueado instantaneamente, sem precisar de reload
- **Limite de gasto**: calculado a partir do mesmo histórico de
  chamadas dos relatórios (manual 18) — soma o tempo de conversa do
  dia por ramal, multiplica por um custo por minuto configurado

## Como configurar
No `docker-compose.yml`, serviço `queue-api`:
```yaml
FRAUD_RATE_WINDOW_SECONDS: "60"    # janela de tempo
FRAUD_RATE_THRESHOLD: "10"         # chamadas externas na janela = alerta
FRAUD_AUTO_BLOCK: "false"          # true = bloqueia o número automaticamente
FRAUD_COST_PER_MINUTE: "0"         # custo estimado por minuto de ligação
FRAUD_DAILY_COST_LIMIT: "0"        # 0 = desabilitado; ex: "50" = R$50/dia por ramal
```

**Bloqueio automático e limite de gasto vêm desligados por padrão** —
o alerta de volume sempre funciona (é só visibilidade, sem efeito
colateral), mas ações que mudam comportamento (bloquear um número,
gerar alerta de gasto) são opt-in, mesmo padrão de segurança do resto
do projeto.

## Onde ver os alertas
Painel operacional (manual 17), novo bloco "Alertas de fraude" — lista
os últimos alertas com tipo, ramal envolvido e detalhe, atualizando a
cada 5 segundos igual ao resto do painel.

## Como testar manualmente
1. Configure `FRAUD_RATE_THRESHOLD: "3"` (baixo, só pra testar rápido)
   e `docker compose up -d`
2. De um ramal, disque `0` + números diferentes repetidamente, mais de
   3 vezes em menos de 60 segundos
3. Confira o painel operacional — deve aparecer um alerta "Volume
   anormal" pra esse ramal
4. Ative `FRAUD_AUTO_BLOCK: "true"`, repita o teste — o último número
   discado deve aparecer bloqueado na lista de bloqueio do painel de
   administração (manual 20) automaticamente
5. Configure `FRAUD_COST_PER_MINUTE` e `FRAUD_DAILY_COST_LIMIT` baixos,
   faça uma chamada atendida longa — confira o alerta de limite de
   gasto

## Teste automatizado
- `queue-api/tests/test_fraud_detection.py` — contagem de volume por
  ramal (janela deslizante, ramais independentes), cálculo de custo
  diário, checagem de limite (desabilitado quando `<= 0`)
- `queue-api/tests/test_fraud_detection_server.py` — bloqueio
  automático e limite de gasto desligados por padrão; a flag de
  bloqueio automático é checada **antes** de chamar a AMI
- `tests/test_docker_compose.py::test_fraud_auto_block_and_spending_limit_disabled_by_default`
- `tests/test_ops_panel.py` — painel operacional busca e renderiza
  os alertas

## Limitações conhecidas (honestidade técnica)
- **Limite de gasto é checado depois que a chamada termina**, não
  durante — não existe interrupção de chamada em andamento; é
  detecção reativa (pós-fato), não prevenção em tempo real dentro da
  própria ligação
- **`CallRateTracker` é só em memória** — reinicia zerado se o
  `queue-api` reiniciar; não é um histórico persistente como os
  relatórios (manual 18)
- **Bloqueio automático não tem "desbloqueio automático"** — uma vez
  bloqueado, alguém precisa desbloquear manualmente pelo painel de
  administração (manual 20), mesmo que o alerta tenha sido um falso
  positivo (ex: uma campanha de discagem legítima)
- **Limiar único pra todos os ramais** — não dá pra configurar um
  limite de volume diferente por ramal ou por setor
- **Custo por minuto é um valor fixo global**, não reflete tarifas
  reais por destino (nacional vs. internacional vs. celular teriam
  custos bem diferentes na vida real)
