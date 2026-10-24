# Manual 116 — Consultas de monitoramento isoladas por tenant

## Objetivo e correções

A extensão de segurança do AXE PABX abrange:

| Endpoint | Proteção |
| --- | --- |
| `GET /api/missed-calls` | Bearer válido + registros associados à empresa |
| `GET /api/fraud-alerts` | Bearer válido + somente alertas de ramais do tenant |
| `GET /api/quality?only_poor=true` | Bearer válido + qualidade de canais da empresa |

As três consultas usam a política de credenciais temporárias do
[Manual 113](manual-113-autenticacao-filas-tenant.md), sem CORS `*`.
`Origin` precisa estar autorizado; respostas protegidas aplicam
`no-store`, `nosniff` e `Vary: Origin`. Filtros URL, como
`?tenant=t2`, **não** mudam a empresa autenticada.

### Atribuição conservadora dos eventos AMI

O módulo `queue-api/monitoring_access.py` identifica tenant **somente**
por campos operacionais completos e coerentes:

- `QueueCallerAbandon`: nome exato `fila-tN[-en|-es]` do evento AMI.
- `DialEnd`: ramal provisionado no canal de origem `PJSIP/tN-...-hex`.
- `QualityStats`: ramal no canal `PJSIP/tN-...-hex`.
- Alertas de fraude: prefixo exato do ramal interno, como `t1-recepcao`.

Se `AccountCode` for informado e contradizer o tenant derivado do
canal/fila, o evento não ganha tenant válido. **Eventos sem proveniência
inequívoca não aparecem nas APIs de monitoramento.** Isso pode resultar
em menos ocorrências exibidas até que o dialplan e o AMI sejam
homologados, mas evita expor dados de outra empresa.

Corrigido também o processamento de chamadas perdidas: a detecção
estava dentro de `check_call_volume` após um retorno antecipado para
eventos que não fossem discagem externa `DialBegin`, impedindo
registro de `QueueCallerAbandon`. Agora é executada no fluxo geral
`handle_ami_event`, antes da notificação, com tenant verificado.

### Destinatários globais de notificações

A versão legada utiliza um SMTP_TO e um WHATSAPP_TO globais. Para
evitar que informações de uma empresa sejam enviadas aos destinatários
de outra, o envio exige **NOTIFY_TENANT** com tenant exato, além
de `NOTIFY_CHANNELS`. Sem `NOTIFY_TENANT`, envio externo permanece
bloqueado inclusive se canais forem habilitados. Uma ocorrência de
outro tenant pode constar do histórico autorizado dele, mas jamais
ser encaminhada ao destinatário global configurado para o primeiro.

No compose, configure por exemplo `NOTIFY_TENANT=t1` **somente**
quando os destinatários globais forem autorizados a receber alertas
de t1. Suporte a destinos distintos por tenant requer evolução futura,
sem utilização insegura dos destinatários globais.

### Interface

Webphone e painel operacional enviam `Authorization: Bearer` apenas
a APIs HTTPS remotas (ou localhost para testes) e não colocam tokens
em URLs. Caller ID, canais, alertas e detalhes são mostrados com
`textContent`, nunca incorporados diretamente como HTML.

### Testes

```bash
cd queue-api
python3 -m pytest -q tests/test_monitoring_tenant_http.py \
  tests/test_missed_calls.py tests/test_fraud_detection.py \
  tests/test_quality_monitoring.py
```

Os testes de HTTP com servidor local cobrem isolamento t1/t2/t10,
ausência de credencial, revogação, preflight/CORS, tentativas de
manipular parâmetros e nomes de rotas; os de AMI verificam
atribuição positiva e rejeição de canais/filas ambíguos. Dados
sintéticos e AMI simulado **não** substituem a homologação real.

### Pendências e GO

* Os eventos AMI de qualidade/customizados e callbacks precisam ser
  validados com dialplan, trunk e instrumentação reais antes de usar
  o painel para decisões operacionais.
* O catálogo de credenciais ainda não está ligado ao login SIP/SSO.
* Campanhas, callbacks, satisfação, envio de notificações e outras
  integrações seguem exigindo revisão de isolamento e autorização.
* Esta PR não encerra o Marco 8, não faz merge nem implantação e
  não concede GO de produção. **Base: 7/16 (43,8%).**
