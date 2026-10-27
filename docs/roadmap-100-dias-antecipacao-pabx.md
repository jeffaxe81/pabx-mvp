# AXE PABX — aceleração planejada de 100 dias

**Objetivo:** antecipar a preparação de 100 dias de trabalho a partir
do Marco 8, sem declarar testes ou releases realizados antecipadamente.
O horizonte abaixo é uma sequência prioritária de entregas **planejadas**,
não percentual executado nem prazo garantido.

| Horizonte | Entrega planejada | Critério para declarar concluída |
| --- | --- | --- |
| D01–D10 | Segurança de presença, pausa, histórico e BLF por empresa (PR em curso) | HTTP negativo/positivo + CI estática e interface + laboratório |
| D11–D20 | Limites dos indicadores e histórico de SLA por tenant | Sem vazamento entre t1/t2/t10 em filtros e agregações |
| D21–D30 | Relatórios CDR/CEL e exportação com controle de papel | Evidências de consistência por tenant, consultas negativas |
| D31–D40 | Callback, discador e campanhas com autenticação e cotas | Nenhum originate fora do tenant, idempotência e auditoria |
| D41–D50 | URA, roteamento e transbordo em fila por empresa | Chamadas reais, inclusive falhas e timeouts |
| D51–D60 | Correio de voz, armazenamento e retenção por tenant | PIN, caixa postal e arquivos provados sem cruzamentos |
| D61–D70 | Backup/restauração e isolamento dos snapshots | Exercício real de restore, RPO/RTO aferidos |
| D71–D80 | Carga, SIP TLS/SRTP e failover progressivo | Métricas e limites de capacidade medidos |
| D81–D90 | RBAC consolidado, emissão de credenciais e auditoria | Rotação/revogação, ações de operador comprovadas |
| D91–D100 | Homologação integrada, evidências e decisão de release | Todos os gates verdes no mesmo SHA, aprovação humana e rollback |

## Regra de execução

1. Entrega técnica não se confunde com homologação ou implantação.
2. Uma PR em rascunho pode avançar enquanto testes de infraestrutura
   não estão finalizados, sem alterar percentual dos marcos fechados.
3. Se algum teste reprovar, a entrega fica aberta; não retirar testes
   nem falsificar evidências para acelerar.
4. Reordenar blocos por dependência e risco é permitido, registrando
   as razões na PR e nos relatórios de acompanhamento.
5. Prioridade técnica a **segurança multiempresa e dados** antes de
   disponibilizar uma operação pública.

**Linha de base no início:** 7/16 marcos concluídos (43,8%); marco 8
aberto; GO operacional não autorizado. A PR do Manual 114 é o
primeiro incremento deste plano, **não** 100 dias de execução terminados.
