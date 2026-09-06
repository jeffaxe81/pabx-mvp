# Manual 11 — Notificação de chamada perdida (backlog #5)

## O que é
Quando uma chamada não é atendida (ninguém atendeu, estava ocupado,
ou o cliente desistiu esperando na fila), o sistema pode avisar
automaticamente por **e-mail** e/ou **WhatsApp**. Além disso, um
histórico das últimas chamadas perdidas aparece na interface web
(painel "Chamadas perdidas"), independente de notificação estar
habilitada ou não.

## Como detecta uma chamada perdida
Dois eventos AMI, ambos gerados nativamente pelo Asterisk:

1. **`DialEnd`** com `DialStatus` diferente de `ANSWER` (`NOANSWER`,
   `BUSY`, `CANCEL`, `CONGESTION`) — cobre chamada direta pro ramal
   1000, chamada entre ramais, e a chamada puxada da fila via pickup
2. **`QueueCallerAbandon`** — o cliente desligou enquanto esperava na
   fila, antes de qualquer atendimento

## Como configurar
Tudo em variáveis de ambiente do serviço `queue-api`
(`docker-compose.yml`). **Por padrão vem tudo desligado**
(`NOTIFY_CHANNELS=""`) — o projeto não deve sair enviando notificação
nenhuma sem credenciais reais configuradas.

Pra habilitar e-mail:
```yaml
NOTIFY_CHANNELS: "email"
SMTP_HOST: "smtp.seuservidor.com"
SMTP_PORT: "587"
SMTP_USERNAME: "seu-usuario"
SMTP_PASSWORD: "sua-senha"
SMTP_FROM: "pabx@suaempresa.com"
SMTP_TO: "telefonista@suaempresa.com"
```

Pra habilitar WhatsApp (via WhatsApp Business Cloud API, da Meta):
```yaml
NOTIFY_CHANNELS: "whatsapp"          # ou "email,whatsapp" pros dois
WHATSAPP_PHONE_NUMBER_ID: "seu-phone-number-id"
WHATSAPP_ACCESS_TOKEN: "seu-token-de-acesso"
WHATSAPP_TO_NUMBER: "5511999999999"
```

O `WHATSAPP_ACCESS_TOKEN` e `WHATSAPP_PHONE_NUMBER_ID` vêm do painel
do WhatsApp Business Platform (Meta for Developers) — configurar isso
está fora do escopo deste projeto.

## Como testar manualmente
1. Configure `NOTIFY_CHANNELS` com pelo menos um canal e credenciais
   reais
2. `docker compose up -d`
3. Ligue pra telefonista (ramal 1000 ou via fila) e **não atenda** de
   propósito até dar timeout, ou recuse a chamada
4. Confira se o e-mail/mensagem do WhatsApp chegou
5. Confira também o painel "Chamadas perdidas" na interface web — deve
   aparecer a entrada, atualizando a cada 10 segundos

Sem configurar nenhum canal, o passo 5 (histórico visual) continua
funcionando normalmente — só a notificação externa fica desligada.

## Teste automatizado
- `queue-api/tests/test_missed_calls.py` — detecção (quais eventos
  contam como chamada perdida) e o histórico em memória (ordenação,
  limite)
- `queue-api/tests/test_notifiers.py` — conteúdo das mensagens
  (e-mail e WhatsApp) e o dispatcher (só envia pelos canais
  habilitados, um canal falhando não trava o outro) — usa mocks, sem
  rede de verdade
- `tests/test_ami_config.py::test_manager_queue_api_user_can_receive_dialend_events`
- `tests/test_docker_compose.py::test_notify_channels_env_present_and_disabled_by_default`
- `tests/test_webphone_html.py::test_missed_calls_polling_starts_and_stops_with_connection`

## Limitações conhecidas (honestidade técnica)
- **`send_email` e `send_whatsapp` (o envio de rede de verdade) não
  têm teste de integração** — só dá pra validar contra um servidor
  SMTP e uma conta do WhatsApp Business reais. Os testes cobrem tudo
  que é determinístico (montagem de mensagem, lógica de quais canais
  disparar) via mocks
- **Um destinatário fixo só** — `SMTP_TO` e `WHATSAPP_TO_NUMBER` são
  únicos, não há lista de destinatários nem regra por horário/tenant
- **Sem retry** — se o envio falhar (rede fora do ar, credencial
  errada), a notificação daquela chamada específica se perde; só fica
  registrado no log do container (`[AVISO] falha ao notificar...`)
- Detecção de chamada perdida via `DialEnd` cobre qualquer `Dial()` no
  dialplan, inclusive chamadas puramente internas entre ramais (ex:
  `1001` ligando pra `1002` sem atender) — se isso gerar notificações
  demais no seu uso real, vale filtrar por destino antes de disparar
