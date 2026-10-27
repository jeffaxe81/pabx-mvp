# Manual 115 — Indicadores, SLA e relatórios CDR isolados por empresa

## Entrega

As consultas `GET /api/metrics/today`, `GET /api/metrics/sla`,
`GET /api/metrics/sla/history` e `GET /api/reports` agora **exigem**
o Bearer temporário do tenant do Manual 113. Sem identidade válida ou
em caso de origem de navegador não autorizada, a API recusa a consulta
em vez de devolver indicadores globais. Todas as respostas passam por
`Cache-Control: no-store`, `Vary: Origin` e CORS por origem exata.

- **Indicadores do dia:** `TenantDailyMetrics` acumula CDRs separados
  exclusivamente pelo campo AMI `AccountCode` (ou `Accountcode`) no
  formato exato `tN`. Se ambas as variantes aparecerem e divergirem,
  o evento é descartado. Evento sem identificador inequívoco **não**
  entra em nenhum tenant. Estatísticas dos demais tenants não são
  somadas nem expostas. Ao virar o dia, todos os acumuladores zeram.
- **SLA atual:** filtra `QueueSLATracker.snapshot()` usando o nome
  completo da fila `fila-tN(-en|-es)` antes de retornar dados.
  `t1` e `t10` não colidem.
- **SLA histórico:** primeiro limita registros pelo tenant proprietário
  da fila, depois aplica o intervalo de datas e só então agrega por
  data/fila. Nunca agrupar todas as empresas para filtrar depois.
- **Relatórios CDR:** impõe `tenant=identity["tenant"]` na consulta do
  servidor, ignorando qualquer `tenant=` declarado na URL. Agrupamento
  por operador, data ou empresa fica restrito ao tenant autenticado.
- **Rotas exatas:** `/api/reportsXXX` e `/api/metrics/sla-evil`
  deixam de ser sinônimos de endpoints válidos.
- **Interfaces:** Webphone, painel operacional e página de relatórios
  enviam Bearer no cabeçalho por HTTPS, sem persistir o token na URL,
  script estático ou armazenamento local. Nomes de agrupamento
  potencialmente externos são escapados antes de renderizar como HTML.

## Testes

`queue-api/tests/test_metric_tenant_http.py` exercita chamadas HTTP
em loopback com estados de t1, t2 e t10, sessões anônimas, CDR sem
identidade, parâmetros falsos, controle CORS, preflight, histórico,
expiração/revogação e virada de dia.

```bash
cd queue-api
python3 -m pytest -q tests/test_metric_tenant_http.py \
  tests/test_metrics.py tests/test_queue_sla.py tests/test_server_routes.py
```

A CI de interface e o laboratório Asterisk também são obrigatórios
para aceitar o mesmo SHA da PR. Testes HTTP locais usam dados sintéticos
e não substituem ligações reais com AccountCode no AMI.

## Limites conhecidos

**Compatibilidade dos CDRs:** se uma implantação existente não propagar
`CDR(accountcode)` até os eventos AMI, o novo indicador diário aparece
zerado em vez de inventar a empresa responsável. Validar o dialplan,
o `cdr_manager.conf` e os eventos concretos do laboratório/cliente,
inclusive ramais dinâmicos e desvio de chamada, antes de confiar nos
valores como completos. O histórico CDR mantém a classificação herdada,
que exige auditoria de proveniência para aceite definitivo.

Rotas legadas **não abordadas** neste incremento, inclusive histórico
de chamadas perdidas, qualidade, fraude, satisfação, campanhas,
callbacks e outros indicadores, ainda exigem auditoria de isolamento.
As permissões de agentes/supervisores seguem as credenciais do
Manual 113, que ainda não são SSO nem identidade SIP criptograficamente
vinculada.

**Sem GO, implantação automática ou merge.** Marco 8 parcial;
programa 7/16 (43,8%).
