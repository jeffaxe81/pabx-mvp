# Manual 117 — Campanhas, callbacks e satisfação por empresa

## Objetivo

Eliminar a chave global como autorização suficiente para consultar
contatos ou originar chamadas da empresa errada.

| Endpoint | Regra |
| --- | --- |
| `GET /api/campaigns`, `GET /api/campaigns/<id>` | Bearer do tenant + chave de originação; supervisor/admin; campanha precisa ter o tenant exato |
| `POST /api/campaigns` | Dupla autorização; tenant é atribuído pelo servidor; ramal precisa pertencer à empresa |
| `POST /api/campaigns/<id>/dial-next` | Dupla autorização, ID, empresa e ramal verificados antes de Originate |
| `GET /api/callbacks` | Dupla autorização, lista somente callbacks com tenant validado |
| `POST /api/callbacks/dial-next` | Dupla autorização e tenant; Originate passa `Variable: TENANT=tN` e `Account: tN` |
| `GET /api/satisfaction` | Bearer de tenant; filtros de operador e agregações aplicados somente após limitar os registros à empresa |

A chave `X-Click-To-Call-Key` continua necessária como fator
operacional para campanhas e callbacks, **mas nunca substitui**
`Authorization: Bearer`. Agentes não podem criar ou disparar listas:
somente `supervisor` e `admin`. Todas essas rotas usam origem CORS
explícita e respostas `no-store`.

### Atribuição AMI e recuperação legada

O dialplan de solicitação de callback envia `Tenant=${TENANT}`. O
queue-api agora valida essa empresa antes de persistir o pedido.
Registros antigos sem campo `tenant` ficam fora das listas autorizadas;
não há tentativa de adivinhar proprietário a partir do telefone.
Campanhas criadas nesta versão recebem o tenant autenticado; registros
antigos sem tenant não ficam visíveis ou discáveis nessa API.

A correlação do resultado `DialEnd` exige `AccountCode` AMI válido
ou canal originador autenticável; sem identificação, não altera nenhuma
campanha/callback. O status pode continuar em *discando* quando o
Asterisk não fornecer um identificador de tenant. Isso é preferível
a marcar resultados na empresa errada; reconciliar com CDR auditado.
O `Originate` passa `Account=tN` e, para callback,
`Variable: TENANT=tN`.

**Atenção ao dialplan:** removido o fallback `t1` na
`[callback-connect]`. Falta do tenant resulta em `Hangup`, nunca
transbordo para a primeira empresa.

### Testes e riscos

```bash
cd queue-api
python3 -m pytest -q tests/test_campaign_tenant_http.py \
  tests/test_campaigns.py tests/test_callbacks.py tests/test_survey.py
```

Os testes executam requisições HTTP em loopback e simulam AMI;
incluem dupla credencial, papéis, t1/t2, tentativas de spoofing,
revogação, Originate, correlação e satisfação. Validação de
roteamento real, discagem no tronco e identificação AccountCode são
necessárias antes de operar com clientes reais.

**Ainda não resolvido:** a rota legada de click-to-call continua com
chave única e requer substituição por credencial específica de tenant.
Também há risco de concorrência nos arquivos JSON das campanhas,
callbacks e resultados; controlar tentativas simultâneas e estado
persistente será uma entrega de hardening adicional. Integração de
autenticação com SIP/SSO e trilha auditável continuam pendentes.

Sem merge/deploy automático ou GO. Marco 8 permanece aberto;
base 7/16 (43,8%).
