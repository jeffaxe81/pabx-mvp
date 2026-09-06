# Manual 19 — Integração CRM: screen-pop PABX→CRM (item #13)

## O que é
Complementa o click-to-call (manual 12, CRM→PABX). Aqui é a direção
contrária: quando uma chamada **chega** pro ramal, o sistema ajuda a
identificar o cliente e abrir o cadastro dele no CRM — sem a
telefonista precisar copiar o número e colar em outro lugar.

Como não há um CRM real integrado neste projeto, implementei o
**mecanismo genérico** dos dois jeitos que um CRM de verdade
costuma consumir:

1. **Link clicável na interface** — a forma mais simples e universal
2. **Webhook do servidor** — pra sistemas headless que quiserem ser
   avisados sem depender do navegador da telefonista

## 1. Link de screen-pop (client-side)
Quando uma chamada chega, aparece um link "Abrir cadastro do cliente
no CRM" na tela — se você configurou a URL do seu CRM na tela de
conexão.

**Por que é um link clicável, não abre sozinho**: a maioria dos
navegadores bloqueia `window.open()` disparado sem um gesto do
usuário (clique). Uma chamada chegando não é um clique — então abrir
automaticamente falharia silenciosamente na maior parte das vezes. Um
link que a telefonista clica é mais confiável e ainda é praticamente
instantâneo.

**Como configurar**: no campo "URL de screen-pop do CRM" na tela de
conexão, use `{numero}` como placeholder pro número de quem está
ligando:
```
https://seu-crm.com/contatos?telefone={numero}
```

## 2. Webhook (server-side)
Pra sistemas que processam a notificação sem envolver o navegador
(ex: um serviço no CRM que já mantém uma tela aberta em outro lugar),
o `queue-api` pode fazer um `POST` assim que a chamada começa a tocar:

```json
{
  "event": "incoming_call",
  "caller_number": "5511988887777",
  "caller_name": "Cliente Teste",
  "operator_extension": "1000"
}
```

**Desligado por padrão** (`CRM_WEBHOOK_URL` vazio). Pra habilitar, no
`docker-compose.yml`:
```yaml
CRM_WEBHOOK_URL: "https://seu-crm.com/webhooks/chamada-recebida"
```

## Como testar manualmente
1. Configure a URL de screen-pop na tela de conexão (pode ser algo
   simples como `https://www.google.com/search?q={numero}` só pra
   testar o mecanismo)
2. Receba uma chamada — o link deve aparecer na tela, com o número
   certo já embutido
3. Clique — deve abrir numa nova aba
4. Pro webhook: configure `CRM_WEBHOOK_URL` apontando pra algo como
   `https://webhook.site` (serviço público de teste), `docker compose up -d`,
   receba uma chamada, confira que o POST chegou

## Teste automatizado
- `queue-api/tests/test_screen_pop.py` — parsing do evento `DialBegin`,
  montagem do payload do webhook, dispatcher isolando falhas sem
  derrubar o resto do processamento de eventos
- `tests/test_webphone_html.py` — link montado a partir do template
  configurável, **nenhum uso de `window.open()`** no arquivo inteiro
  (garantia de que a decisão de "link clicável, não popup automático"
  não regride), os dois pontos de chamada recebida (linha 1 e linha 2)
  configuram o link
- `tests/test_docker_compose.py::test_crm_webhook_disabled_by_default`

## Limitações conhecidas (honestidade técnica)
- **Não identifica o cliente de verdade** — só repassa o número; quem
  faz a busca "esse número pertence a qual cliente" é o CRM do outro
  lado, não este projeto
- **Envio do webhook não tem teste de integração real** — mesma
  situação já documentada pro resto das integrações de rede deste
  projeto (AMI, SMTP, WhatsApp, tronco TDM)
- **Sem retry** no webhook — se o CRM estiver fora do ar no momento
  exato da chamada, a notificação daquela chamada específica se perde
- **`DialBegin` dispara pra qualquer `Dial()`**, inclusive chamadas
  puramente internas entre ramais — se isso gerar webhooks demais no
  seu uso real, vale filtrar por destino antes de disparar (mesma
  observação já feita sobre `DialEnd` no manual 11)
- Template da URL só suporta um placeholder (`{numero}`) — nomes,
  contexto de tenant, etc. não são passados pro CRM neste MVP
