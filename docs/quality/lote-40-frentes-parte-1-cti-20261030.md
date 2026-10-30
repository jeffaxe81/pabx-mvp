# AXE PABX — Lote 1 de 2: 20 frentes CTI/Originate (40 frentes solicitadas)

**Data:** 30/10/2026. **Status:** CODE_REGISTERED_PENDING_REAL_HOMOLOGATION.
**Especialidades:** CTI/CRM, segurança de SIP, autenticação multiempresa, backend AMI, resiliência e testes.

O click-to-call já funcionava com Bearer + chave de API. Este lote não cria um novo discador: aumenta a segurança e a robustez da função real existente, `POST /api/click-to-call`, sem modificar dialplan, mídia ou chamadas receptivas.

## 20 frentes implementadas

| Nº | Frente técnica | Implementação |
|---:|---|---|
| 01 | CTI / entrada | Rejeitar texto livre junto ao telefone, evitando discagem silenciosamente alterada |
| 02 | CTI / entrada | Rejeitar múltiplos sinais `+` e caracteres especiais ambíguos |
| 03 | CTI / entrada | Limitar tamanho bruto da entrada antes de normalização |
| 04 | Telefonia / E.164 | Preservar dígitos e formatação numérica conhecida, com limite de 15 dígitos |
| 05 | API | Comparar chave operacional com `hmac.compare_digest` |
| 06 | API | Recusar chave operacional de tipo inadequado ou comprimento abusivo |
| 07 | Ramais | Exigir extensão com padrão de tenant integral e caracteres seguros |
| 08 | Multiempresa | Revalidar ramal permitido e identidade Bearer existente antes da originação |
| 09 | CTI / rastreio | Novo header opcional `X-Idempotency-Key` no click-to-call |
| 10 | CTI / rastreio | Idempotência só no mesmo tenant e no mesmo ramal/número |
| 11 | CTI / rastreio | Repetição após aceite explícito retorna `duplicate=true` sem novo AMI |
| 12 | CTI / concorrência | Solicitação idêntica ainda em curso retorna conflito 409 |
| 13 | CTI / concorrência | Mesmo request ID com dados diferentes retorna conflito 409 |
| 14 | Resiliência AMI | Timeout/erro de transporte fica indeterminado, sem retentar automaticamente |
| 15 | Resiliência AMI | Rejeição explícita libera o request ID para nova tentativa |
| 16 | Controle de tráfego | Limite de originações por empresa por minuto (padrão: 30) |
| 17 | Controle de tráfego | Limite de originações por ramal por minuto (padrão: 10) |
| 18 | Concorrência | Limite de originações em andamento por processo (padrão: 50) |
| 19 | Segurança de estado | Contadores/idempotência com TTL e limites de memória |
| 20 | Segurança de estado | Bloquear novas originações se o relógio monotônico regredir ou for inválido |

A suíte da API existente recebe testes de idempotência por t1/t2, repetição, conflito, 429 e timeout AMI, além de novos testes concorrentes e de limitação em `test_outbound_admission.py`.

## API

Requisição idempotente (opcional, para sistemas que possam repetir pedidos por timeout):

```bash
curl -X POST https://pabx.exemplo.invalid/api/click-to-call \
  -H "Authorization: Bearer $QUEUE_BEARER" \
  -H "X-Click-To-Call-Key: $CTI_KEY" \
  -H "X-Idempotency-Key: crm-ordem-00000001" \
  -H "Content-Type: application/json" \
  --data '{"extension":"t1-recepcao","number":"11999998888"}'
```

O endereço é **fictício**. Nunca incorporar tokens e chaves em URLs, commits ou registros de log. `200 duplicate=true` significa que o **AMI aceitou a ação anterior**; não comprova que a chamada foi completada, atendida ou gravada. `409` indica idempotência em andamento, incerta ou conflitante. `429` indica limite por processo. `502` após timeout indica resultado desconhecido, não chamada perdida com certeza.

## Limitações

- **Proteção somente em memória de um processo.** Em múltiplos workers/instâncias, exige coordenação externa persistente, como cache transacional ou banco; a atual camada não concede garantias de exactly-once em um cluster.
- O `X-Idempotency-Key` é opcional para preservar clientes existentes. Sem ele, a proteção é de volume e simultaneidade, **não há deduplicação automática de chamadas**.
- Limites por minuto são conservadores e precisam de dimensionamento específico na operação. **Não há homologação de chamadas, trilhas de gravação, áudio ou STIR/SHAKEN**.
- A chave secundária de CTI é global no desenho existente; o Bearer do tenant continua mandatório. A solução futura de maior porte deve usar autenticação de aplicativos por tenant e auditoria de chamadas por `ActionID`.
- Esta PR **não altera** campanhas/callbacks e não valida uso real da operadora.
- **15 provas operacionais reais seguem pendentes, 7/16 marcos (43,8%).** Sem aprovação de produção.

Arquivos: `queue-api/outbound_admission.py`, `queue-api/click_to_call.py`, `queue-api/server.py`, `queue-api/tests/test_click_to_call.py`, `queue-api/tests/test_outbound_admission.py`, `queue-api/tests/test_campaign_tenant_http.py`.
