# Manual 18 — Relatórios por atendente, tenant e período (item #12)

## O que é
Diferente das métricas do dia (manual 13, que só mostram "hoje" e
zeram à meia-noite), isso é um **histórico persistente**: toda
chamada finalizada vira um registro guardado em disco, e dá pra
consultar por período (`De`/`Até`) e agrupar por **atendente** ou
**tenant** — respondendo perguntas como "quantas chamadas cada
telefonista atendeu na semana passada" ou "qual tenant recebeu mais
ligações no mês".

## Como funciona
- Cada evento CDR (o mesmo que já alimenta as métricas do dia) agora
  também vira um registro em `call_log.jsonl` — um JSON por linha,
  com data, atendente, tenant, se foi atendida e por quanto tempo
- **Atendente e tenant são extraídos automaticamente** do canal que
  atendeu a chamada: `PJSIP/t1-recepcao-00000003` vira atendente
  `t1-recepcao`, tenant `t1` (o prefixo `t1-` é o mesmo padrão usado
  em todo o resto do projeto)
- O arquivo fica num volume Docker separado (`queue_api_data`), então
  sobrevive a um restart do container — diferente das métricas do dia,
  que são só em memória

## Como consultar
Interface web em `webphone/relatorios.html`:
```
http://<ip-do-servidor>:8082/relatorios.html?api=http://<ip-do-servidor>:8090
```
Também tem um link "Ver relatórios históricos" no painel operacional
(manual 17), que já leva o endereço da API configurado.

Ou direto pela API:
```bash
# Total agregado do período
curl "http://<ip-do-servidor>:8090/api/reports?start=2024-01-01&end=2024-01-31"

# Agrupado por atendente
curl "http://<ip-do-servidor>:8090/api/reports?start=2024-01-01&end=2024-01-31&group_by=operator"

# Agrupado por tenant
curl "http://<ip-do-servidor>:8090/api/reports?group_by=tenant"
```

## Como testar manualmente
1. `docker compose up -d`
2. Faça algumas chamadas variadas: atendidas, não atendidas, de
   ramais diferentes
3. Abra os relatórios, deixe o período como "hoje", clique "Gerar" —
   confira que o total bate com o que você fez
4. Troque "Agrupar por" para "Atendente" — confira que aparece uma
   linha por telefonista que atendeu algo
5. Reinicie o container `queue-api` (`docker compose restart queue-api`)
   e gere o relatório de novo — os dados **devem continuar lá**
   (diferente das métricas do dia, que reiniciam zeradas)

## Teste automatizado
- `queue-api/tests/test_reports.py` — extração de atendente/tenant a
  partir do nome do canal, parsing do CDR pra registro de relatório,
  `CallLogStore` (persistência, filtro por período/atendente/tenant,
  resiliência a linha corrompida), `aggregate`/`group_by`
- `tests/test_reports_html.py` — IDs da interface, opções de
  agrupamento batem com o que o backend aceita, link a partir do
  painel operacional propaga a URL da API
- `tests/test_docker_compose.py::test_queue_api_has_persistent_volume_for_call_log`

## Limitações conhecidas (honestidade técnica)
- **Extração de atendente por regex no nome do canal** — funciona bem
  com o padrão de nomenclatura do Asterisk (`Tech/Resource-Sequência`),
  mas não é robusto a mudanças de driver de canal ou nomenclaturas
  não-padrão
- **Arquivo `.jsonl` cresce indefinidamente** — não há rotação nem
  expurgo automático; num uso real por muitos meses, vale monitorar o
  tamanho ou implementar rotação
- **Sem paginação na API** — `/api/reports` sem agrupamento carrega
  todo o arquivo pra memória a cada consulta; aceitável pro volume de
  um MVP, não pra milhões de registros
- **Sem exportação** (CSV/Excel) — só visualização na tela ou JSON cru
  da API
- Chamadas que não batem no padrão de canal esperado (ex: chamadas
  puramente internas entre dois ramais comuns) aparecem sem atendente/
  tenant identificado, agrupadas como "desconhecido"
