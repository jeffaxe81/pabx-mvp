# Campanha de 500 testes — AXE PABX

> Plano de casos, **não** 500 testes executados. Cada caso exige implementação de teste automatizado ou roteiro reproduzível e resultado registrado.

Escopo: PABX puro, sem funcionalidades de Contact Center ou IA. Evitar repetição de casos já existentes; conferir suíte atual antes de implementar.

| Frente | IDs | Quantidade | Situação |
|---|---|---:|---|
| Discagem e políticas | T001–T080 | 80 | A mapear e executar |
| Troncos SIP e failover | T081–T145 | 65 | A mapear e executar |
| Multiempresa e isolamento | T146–T210 | 65 | A mapear e executar |
| Ramais e autenticação | T211–T270 | 60 | A mapear e executar |
| Transferência e funcionalidades PABX | T271–T325 | 55 | A mapear e executar |
| Provisionamento | T326–T370 | 45 | A mapear e executar |
| CDR, gravação e auditoria | T371–T415 | 45 | A mapear e executar |
| Backup, rollback e disponibilidade | T416–T460 | 45 | A mapear e executar |
| API administrativa e segurança | T461–T500 | 40 | A mapear e executar |

**Total planejado: 500. Executados por esta campanha: 0 (ainda não verificados).**

## Critérios de execução

- Identificar casos existentes antes de gerar novos, evitando testes duplicados.
- Para cada ID: descrição, pré-condição, entrada, resultado esperado, script ou evidência, resultado real e commit.
- Distinguir teste estático de teste SIP/RTP real; não chamar testes estáticos de homologação de chamadas.
- Bloqueio internacional: testar tenant t1, t2 e t3+; rota principal e alternativa; políticas bloqueada e liberada; entradas inválidas.
- Executar CI completa e registrar links das execuções e falhas; manter release aberta até fechamento de critérios REL-01 a REL-20.
