# AXE PABX — 20 entregas de fechamento da release

**Estado:** meta intermediária atingida (6/20 concluídas, 30%). Itens restantes exigem evidência verificável. **Não declarar release concluída apenas por registrar esta lista.**

**Escopo:** PABX puro. Contact Center e IA permanecem no backlog. Implantação inicial local; produção exige aceite específico.

- [x] **REL-01 — Escopo congelado:** PABX puro; CC e IA fora da release. **Estado:** CONCLUÍDO (escopo confirmado nesta release).
- [x] **REL-02 — Inventário da release:** Inventário verificável em docs/release-inventario-pr311.md. **Estado:** CONCLUÍDO.
- [ ] **REL-03 — Auditoria de duplicidade:** Reconciliar roadmap de 100 candidatos com funcionalidades existentes. **Estado:** PENDENTE.
- [ ] **REL-04 — Correção de discagem internacional:** Validar prefixos e regra AstDB por tenant. **Estado:** PENDENTE.
- [ ] **REL-05 — Rota alternativa:** Impedir bypass da política por gateway secundário. **Estado:** PENDENTE.
- [x] **REL-06 — Tenant dinâmico:** O wizard gera para t3/t4/t99 o contexto de saída com TENANT explícito, Gosub(politica-externa,s,1), validação de GOSUB_RETVAL e Dial apenas após autorização. Testes executáveis de geração/validação aprovados na PR #312 (CI de política 41257306083; CI estática 41257306065). Laboratório Asterisk da mesma PR validou SIP geral com t3, mas não chamadas SIP específicas de bloqueio internacional. **Estado:** CONCLUÍDO no escopo de integração do wizard.
- [x] **REL-07 — Isolamento multiempresa:** Contextos t1/t2 possuem TENANT e famílias blocklist independentes; a política consulta politica-externa-${TENANT}/internacional. Testes de isolamento e geração t3/t4/t99 aprovados na PR #312 (41257306083), e laboratório Asterisk da mesma PR validou tentativas SIP cruzadas entre empresas (41257306027). **Estado:** CONCLUÍDO para isolamento de contextos/identidade e segregação das chaves AstDB no código; não equivale a ensaio SIP específico de política de bloqueio, ainda pendente em REL-12/14.
- [ ] **REL-08 — Segurança de entradas:** Validar TENANT, DESTINO e contexto SIP. **Estado:** PENDENTE.
- [ ] **REL-09 — Permissões administrativas:** Restringir quem pode alterar políticas de saída. **Estado:** PENDENTE.
- [ ] **REL-10 — Logs e auditoria:** Registrar decisões de bloqueio sem expor credenciais. **Estado:** PENDENTE.
- [x] **REL-11 — Testes unitários inéditos:** Cobertura estática de decisões ALLOW/DENY e entradas inválidas, testes isolados do preflight e 30 cenários parametrizados de reconhecimento de contextos. **Estado:** CONCLUÍDO NO ESCOPO DE TESTES AUTOMATIZADOS, com CI específica aprovada; NÃO comprova comportamento de chamadas SIP reais (REL-12 permanece pendente). Evidência: commit `ebd79c3a`, workflow `41254672287`, job `124695200214` SUCCESS.
- [ ] **REL-12 — Testes de integração dialplan:** Executar chamadas simuladas em laboratório Asterisk. **Estado:** PENDENTE.
- [ ] **REL-13 — Regressão de telefonia:** Conferir chamadas internas, externas e transferências. **Estado:** PENDENTE.
- [ ] **REL-14 — Regressão de troncos:** Validar gateway principal e alternativo. **Estado:** PENDENTE.
- [ ] **REL-15 — Regressão de provisionamento:** Confirmar geração e isolamento de terminais. **Estado:** PENDENTE.
- [ ] **REL-16 — Backup pré-release:** Gerar e verificar backup restaurável. **Estado:** PENDENTE.
- [ ] **REL-17 — Rollback:** Documentar e testar retorno à versão anterior. **Estado:** PENDENTE.
- [ ] **REL-18 — Segurança de configuração:** Revisar senhas padrão, TLS e permissões. **Estado:** PENDENTE.
- [x] **REL-19 — CI geral e laboratório automatizado:** 18/18 jobs aprovados no head da PR #311: workflow 41255379752 (8/8 laboratório Asterisk), 41255379878 (8/8 validação estática), 41255379848 (1/1 política), 41255379887 (1/1 auditoria). **Estado:** CONCLUÍDO no escopo de CI/laboratório geral; não substitui homologação SIP específica REL-12 a REL-14 nem produção.
- [ ] **REL-20 — Release candidate local:** Gerar tag/versão e checklist de aceite, sem publicar em produção. **Estado:** PENDENTE.

## Barra de progresso — 2026-10-31 (meta intermediária)

`[############----------------------------] 30% (6/20)`

**Parcial em código, não homologado:** REL-04, REL-05 e REL-08 (novos testes de entradas inválidas). **CI específica, CI geral e laboratório automatizado aprovados (REL-19); homologação SIP específica ainda pendente:** REL-12 a REL-14. Não contar itens parciais como entregues.

**Evidência do fechamento de 30%:** PR #312 integrada à main via squash `ef0ec20c43450ad717da8cbb468de535a282d5e1` após aprovação de 17/17 jobs: regressão da política (1/1, workflow 41257306083), CI estática (8/8, 41257306065) e laboratório Asterisk (8/8, 41257306027). Alterações incluem `Return(ALLOW)` e `Return(DENY)` explícitos, além de testes de isolamento e do wizard. Não houve implantação em produção nem teste de chamada externa por tronco físico. A homologação específica de bloqueio internacional por SIP/AstDB continua pendente nas REL-04, REL-12 e REL-14.\n\n**Auditoria automatizada REL-03:** workflow `41255085879` aprovado; artefato `auditoria-roadmap-pabx` (ID `13062723149`) contém triagem dos 100 candidatos com status REVISAR_MANUALMENTE. Isto não conclui REL-03, pois a revisão manual e deduplicação ainda faltam.\n\n**Evidências atualizadas:** PR #311. O commit `24462cc7` passou nas duas pipelines, com 16/16 jobs concluídos com sucesso (8 estáticos e 8 de laboratório Asterisk), incluindo Chromium WSS/DTLS-SRTP. A homologação funcional específica de política internacional permanece pendente. O commit `3c15c703` concluiu 16/16 jobs com sucesso (validação estática e laboratório geral Asterisk). O commit `d9756baf` adicionou três verificações estáticas de política. O commit `00a7fc6f` acrescentou cinco regressões estáticas de autorização e rota alternativa. **A CI específica da política externa passou no commit `ebd79c3a` (workflow `41254672287`); a CI geral e os testes SIP funcionais seguem separados e pendentes.** Não confundir aprovação da suíte geral com homologação SIP específica de bloqueio internacional.

## Critério de encerramento

Cada entrega exige referência a commit/PR, evidência de teste aplicável e aprovação. O item REL-20 só fecha depois de REL-01 a REL-19 aprovados; não confundir CI de documentação com homologação funcional.
