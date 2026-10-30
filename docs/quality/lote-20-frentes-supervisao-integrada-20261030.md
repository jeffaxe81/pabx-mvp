# AXE PABX — lote de 20 frentes: supervisão operacional multiempresa

**Registrado em:** 30/10/2026. **Status:** `CODE_REGISTERED_PENDING_REAL_HOMOLOGATION`.

Este lote implementa um recurso operacional integrado, diferente dos 110 relatórios offline anteriores: **endpoint HTTP com autenticação Bearer de fila + painel web de supervisão**, reunindo **20 indicadores de quatro fontes**. Os indicadores são visões derivadas das estruturas existentes no processo `queue-api` e **não** significam 20 novos módulos de telefonia completos.

## Endpoint e interface

`GET /api/supervision/summary` — somente papéis **supervisor** e **admin**, autenticados pelo catálogo privado `queue_access.json`, usando `_require_queue_identity`. Não há token hardcoded nem parâmetro para escolher o tenant. O backend deriva o tenant exclusivamente da credencial Bearer, obedece à allowlist `QUEUE_CORS_ORIGINS`, devolve `Cache-Control: no-store` e mantém política de falhar fechado (401 não autenticado, 403 papel/origem inválidos, 503 fontes inválidas).

Tela `webphone/painel-operacional.html`: novo painel de 4 seções (20 campos). O token permanece apenas no campo em memória da página, nunca na URL ou no localStorage. Trocar ou revogar a credencial impede a repintura por resposta atrasada; o resultado de supervisão tem autorização própria e, se negado, só a seção adicional é ocultada, sem afetar as demais informações previamente permitidas ao agente.

## As 20 frentes em código

| Nº | Área | Campo JSON | Indicador |
|---:|---|---|---|
| 01 | Filas | `waiting_calls` | Chamadas aguardando nas filas do tenant |
| 02 | Filas | `queues_with_waiting` | Quantidade de filas com espera |
| 03 | Filas | `waiting_above_sla_threshold` | Chamadas cujo tempo de espera supera o limiar configurado |
| 04 | Filas | `waiting_over_60_seconds` | Chamadas aguardando mais de 60 segundos |
| 05 | Filas | `longest_wait_seconds` | Maior espera medida em segundos |
| 06 | Ramais | `monitored_extensions` | Ramais observados no contexto BLF do tenant |
| 07 | Ramais | `free_extensions` | Ramais livres |
| 08 | Ramais | `ringing_extensions` | Ramais tocando |
| 09 | Ramais | `busy_extensions` | Ramais em uso ou ocupados |
| 10 | Ramais | `unavailable_extensions` | Ramais indisponíveis |
| 11 | SLA | `offered_calls` | Chamadas oferecidas no tracker de SLA atual |
| 12 | SLA | `within_sla_calls` | Chamadas dentro do limiar de SLA |
| 13 | SLA | `outside_sla_calls` | Chamadas fora do limiar |
| 14 | SLA | `weighted_sla_percent` | Taxa ponderada pelas chamadas oferecidas |
| 15 | SLA | `queues_below_reference_80` | Filas abaixo da referência ilustrativa de 80% |
| 16 | Ocorrências | `missed_events_in_buffer` | Eventos de chamadas perdidas no buffer limitado |
| 17 | Ocorrências | `fraud_alerts_in_buffer` | Alertas de fraude no buffer limitado |
| 18 | Ocorrências | `poor_quality_samples_in_buffer` | Amostras de qualidade ruim no buffer limitado |
| 19 | Ocorrências | `paused_agents_snapshot` | Agentes com estado de pausa atual |
| 20 | Ocorrências | `manual_absent_overrides` | Estados manuais marcados como ausente |

## Proteções aplicadas

1. Isolamento por fila usando `queue_tenant` com nome completo; `fila-t1` não inclui `fila-t10`.
2. BLF só do contexto de hints da credencial; estados do tenant oposto são excluídos.
3. Dados de SLA só de filas vinculadas à credencial, e percentuais são recalculados de `offered` / `within_sla`.
4. Logs de perdas, fraude e qualidade são novamente filtrados no agregador por `tenant` explícito.
5. Pausas e estados manuais só contam ramais atribuídos por `extension_tenant`, sem expor IDs, nomes ou motivos.
6. Resposta não contém CallerID, telefone, canal, IP, nome do cliente, gravações, credenciais, notas, histórico individual nem identificadores de ramal.
7. Falhas de leitura de presença ou de snapshot retornam erro genérico, não valores inventados nem dados particulares.
8. Nenhum evento AMI é emitido; apenas agregações de estado **em memória** já existente.
9. Testes HTTP de isolamento t1/t10, papéis, origem permitida, revogação e privacidade são acrescentados à suíte já existente. CI precisa estar totalmente aprovada antes de merge.

## Limitações e status de produção

- Os 20 indicadores vêm de **snapshots de processo**, atualizados pelo polling existente do painel; não são histórico completo nem prova de disponibilidade em tempo real (inclusive em múltiplas réplicas).
- O buffer de perdas/fraude/qualidade contém apenas o subconjunto retido em memória; `0` não significa ausência universal de incidentes.
- O limiar de **80% é apenas referência ilustrativa**, não meta contratual de um cliente.
- O total de 110 relatórios locais não muda: os 20 itens desta PR são **campos do novo resumo autenticado**, não 20 novos relatórios da CLI.
- Os **15 cenários de prova operacional em ambiente real** da issue #173 continuam diferidos; **7/16 marcos (43,8%)**.
- **Sem implantação em produção** e `operational_go_authorized=false`. Exigir certificados válidos, homologação end-to-end, revisão de acesso e aceite humano antes de GO.

Arquivos modificados: `queue-api/supervision_summary.py` (novo), `queue-api/server.py`, `webphone/painel-operacional.html`, `queue-api/tests/test_monitoring_tenant_http.py` e este documento.
