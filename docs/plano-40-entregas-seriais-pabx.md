# Plano serial de 40 entregas — PABX puro

Escopo: telefonia PABX, sem Contact Center ou IA. Execução **serial**: cada etapa exige evidência e aprovação antes da próxima. Este arquivo é um plano, **não** comprovação de implementação.

| Ordem | Entrega | Situação | Critério de aceite |
|---:|---|---|---|
| 1 | Auditar contexto politica-externa | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 2 | Auditar discagem t1 | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 3 | Auditar discagem t2 | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 4 | Verificar dialplan gerado por tenant | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 5 | Validar preflight Asterisk CLI | Parcial: script implementado, CI pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 6 | Validar falha de contexto ausente | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 7 | Validar cabeçalho CLI real | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 8 | Validar leitura AstDB t1 | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 9 | Validar leitura AstDB t2 | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 10 | Distinguir AstDB ausente de erro CLI | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 11 | Testar bloqueio internacional t1 | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 12 | Testar permissão internacional t1 | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 13 | Testar bloqueio internacional t2 | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 14 | Testar permissão internacional t2 | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 15 | Testar independência t1/t2 | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 16 | Testar discagem nacional t1 | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 17 | Testar discagem nacional t2 | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 18 | Testar destino vazio | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 19 | Testar tenant inválido | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 20 | Testar destino com caracteres inválidos | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 21 | Testar prefixo 00 | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 22 | Testar prefixo de acesso 0 | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 23 | Testar seletor de tronco alternativo | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 24 | Testar bloqueio antes do roteamento | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 25 | Testar bloqueio após normalização | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 26 | Testar blocklist t1 | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 27 | Testar blocklist t2 | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 28 | Testar isolamento de blocklists | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 29 | Testar indisponibilidade gateway principal | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 30 | Testar indisponibilidade gateway alternativo | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 31 | Verificar ausência de bypass | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 32 | Verificar CDR de chamadas negadas | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 33 | Verificar CDR de chamadas permitidas | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 34 | Verificar logs de auditoria | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 35 | Validar sintaxe dialplan | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 36 | Validar reload controlado | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 37 | Validar rollback AstDB | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 38 | Validar rollback dialplan | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 39 | Reexecutar regressão PABX | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |
| 40 | Consolidar evidências e decisão release | Pendente | Evidência registrada, teste reproduzível e ausência de regressão |

## Regras de fechamento

- Não confundir testes simulados, testes de integração e chamadas SIP reais.
- Não marcar como homologada uma etapa com CI pendente ou sem evidência correspondente.
- Não efetuar implantação em produção antes de validar rollback e obter autorização.
- Registrar SHA, resultado e limitações por etapa.
