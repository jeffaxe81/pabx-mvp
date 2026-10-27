# Manual 118 — Click-to-call com autorização por tenant e serialização

## O que mudou

A rota de CRM externo `POST /api/click-to-call` **não aceita mais**
`X-Click-To-Call-Key` como única autorização. São necessários:

- `Authorization: Bearer <credencial temporária>`, emitida para um
  tenant e papel válidos pela política do Manual 113;
- `X-Click-To-Call-Key`, a chave operacional compartilhada já existente;
- JSON `{"extension":"t1-recepcao","number":"11999998888"}`
  com ramal cadastrado na allowlist do click-to-call **e** pertencente
  à identidade autenticada (agente: apenas seu próprio ramal; supervisor
  e admin: ramais da mesma empresa).

Exemplo de headers (não substitua valores por credenciais reais em
logs públicos):

```http
POST /api/click-to-call HTTP/1.1
Authorization: Bearer <TOKEN_DA_EMPRESA>
X-Click-To-Call-Key: <CHAVE_OPERACIONAL>
Content-Type: application/json
```

A chamada AMI `Originate` recebe `Account=tN` e `Variable=TENANT=tN`.
Credencial ausente/inválida, origem de navegador não autorizada,
ramal de outra empresa, JSON inválido, corpo vazio/acima de 16 KiB e
chave operacional incorreta são recusados **antes** de qualquer AMI.
Respostas usam CORS por origem aprovada e `Cache-Control: no-store`.
O preflight permite `X-Click-To-Call-Key` apenas para APIs de originação.
Não persistir credenciais em parâmetros URL ou JavaScript estático.

**Quebra de compatibilidade deliberada:** CRMs que chamavam apenas com a
chave de API passarão a receber **401** até receberem uma credencial
de tenant apropriada. Não liberar a rota antiga como fallback.

## Corrida de disparos duplicados

A API usa `OUTBOUND_LOCK` (RLock do processo) para serializar:
1. Consultar o primeiro contato/callback pendente no tenant.
2. Validar que a chamada pertence ao tenant e marcar como `discando`
   no armazenamento.
3. Enviar a ação AMI de originação e retornar o resultado.

O mesmo lock protege criação de campanhas, chegada de novos pedidos de
callback e reconciliação de eventos DialEnd. Assim, duas threads HTTP no
**mesmo processo** não podem selecionar o mesmo primeiro contato antes
de registrar a reserva. Testes integram duas chamadas HTTP simultâneas
com AMI simulado e validam que somente uma originação ocorre.

## Limitações explícitas

- **Não há garantia cross-process/multi-réplica.** Serviços
  queue-api executados em múltiplos processos/hosts com os mesmos
  arquivos JSON ainda necessitam locks compartilhados, escrita
  transacional/atômica e chave de idempotência no armazenamento.
- Uma resposta de AMI incerta ou queda do processo **não** remove
  automaticamente a reserva; deixar o contato como `discando` evita
  originar inadvertidamente duas vezes. Reconciliação manual auditada
  e mecanismo de timeout/recuperação segura são pendências.
- Testes locais simulam AMI; validar SIP/TLS, AccountCode, DTLS-SRTP e
  failover no Asterisk antes do GO.

### Teste direcionado

```bash
cd queue-api
python3 -m pytest -q tests/test_campaign_tenant_http.py \
    tests/test_click_to_call.py tests/test_server_routes.py
```

PR derivada da #71, em rascunho. Sem merge automático, implantação ou
GO de produção. O Marco 8 continua aberto; progresso formal 7/16.
