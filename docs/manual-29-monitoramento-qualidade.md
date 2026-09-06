# Manual 29 — Monitoramento de qualidade de chamada (item #34)

## O que é
Indicadores de qualidade técnica de cada chamada da telefonista —
**jitter** (variação no tempo de chegada dos pacotes de áudio),
**perda de pacotes** e **RTT** (tempo de ida e volta, latência) — com
alerta automático quando algum valor passa de um limiar aceitável.
Isso é diagnóstico de rede, não de atendimento — ajuda a responder
"a ligação caiu/travou por causa da nossa internet, ou foi coisa do
cliente?".

## Como funciona
O Asterisk já coleta essas métricas via **RTCP** (o canal de controle
que acompanha o áudio RTP) durante qualquer chamada — só precisava de
um jeito de capturar isso no momento certo:

1. Nos pontos onde a telefonista fala com o cliente (ramal `1000`,
   `1010`, `1011`, e a chamada puxada da fila), o dialplan registra um
   **hangup handler** (`CHANNEL(hangup_handler_push)`) antes de discar
2. Quando a chamada termina, o handler roda automaticamente: lê
   `${CHANNEL(rtcp,rxjitter)}`, `${CHANNEL(rtcp,rxploss)}` e
   `${CHANNEL(rtcp,rtt)}`, e manda tudo como um evento customizado via
   `UserEvent(QualityStats,...)`
3. O `queue-api` (que já escuta eventos AMI da classe `user`) recebe
   esse evento, compara com os limiares configurados, e guarda no
   histórico — marcando como "ruim" se algum valor passar do limite

## Como configurar
```yaml
QUALITY_JITTER_THRESHOLD_MS: "30"           # jitter acima disso = ruim
QUALITY_PACKET_LOSS_THRESHOLD_PERCENT: "3"  # perda acima disso = ruim
```
Diferente de fraude/backup, **isso já vem ativo por padrão** — é só
visibilidade, sem nenhuma ação com efeito colateral (não bloqueia
nada, não desliga nada), então não faz sentido vir desligado.

## Onde ver
Painel operacional (manual 17), bloco "Qualidade de chamada" — mostra
só as chamadas marcadas como ruins (não lista toda chamada normal,
seria ruído). Também dá pra consultar tudo via API:
```bash
curl "http://<ip>:8090/api/quality"                # tudo
curl "http://<ip>:8090/api/quality?only_poor=true"  # só as ruins
```

## Como testar manualmente
1. `docker compose up -d`
2. Faça uma chamada normal até a telefonista, converse um pouco,
   desligue
3. Confira `/api/quality` — deve aparecer um registro com as métricas
   (mesmo que "boas", `poor: false`)
4. Simular rede ruim de propósito é mais difícil sem ferramentas de
   shaping de rede (`tc`/`netem` no Linux) — se quiser forçar o
   cenário, introduza perda de pacotes artificialmente na rede entre
   os softphones e o servidor e repita o teste; o alerta deve aparecer
   marcado como `poor: true` e no painel operacional

## Teste automatizado
- `queue-api/tests/test_quality_monitoring.py` — parsing do evento
  (inclusive quando o RTCP vem vazio - não deve virar `0.0`, que
  pareceria "qualidade perfeita" por engano), lógica de limiar
  (métrica ausente nunca dispara alarme falso), histórico com filtro
  "só as ruins"
- `tests/test_extensions_conf.py` — os pontos certos empurram o
  hangup handler, o contexto de qualidade lê os campos RTCP certos e
  manda o `UserEvent`
- `tests/test_docker_compose.py::test_quality_monitoring_thresholds_configured`
- `tests/test_ops_panel.py` — painel operacional busca e filtra só as
  chamadas ruins

## Limitações conhecidas (honestidade técnica)
- **Sem teste de integração real** — mesma situação de sempre pras
  partes que dependem do Asterisk de verdade rodando: só valida
  parsing/lógica, não o comportamento real do RTCP
- **Só ramais da telefonista** (1000/1010/1011/pickup) — chamadas
  puramente internas entre ramais comuns não têm o hangup handler,
  então não geram dado de qualidade
- **RTCP pode vir vazio** em chamadas muito curtas, alguns codecs, ou
  quando o outro lado não suporta RTCP — nesses casos não há alerta
  nem "tudo bem", simplesmente não há dado (documentado no código
  como decisão consciente: ausência de dado não deve virar alarme
  falso nem falso positivo de "está tudo ótimo")
- **Sem histórico persistente** — assim como os alertas de fraude, o
  `QualityLog` é só em memória, reinicia zerado se o `queue-api`
  reiniciar
- **Um limiar global**, não por ramal, tenant ou tipo de rede
