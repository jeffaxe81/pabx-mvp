# REL-02 — Inventário verificável da PR #311

**Data-base:** 31/10/2026. **Origem:** relação de arquivos alterados da PR #311 consultada diretamente no GitHub. **Escopo:** PABX puro.

## Código e configuração (3)
- `asterisk/dialplan_politica_externa.conf` — política de saída por tenant, decisão padrão DENY e regra AstDB.
- `asterisk/extensions.conf` — inclusão da política em tenants estáticos e na rota alternativa.
- `admin-api/tenants.py` — geração da política para tenants criados pelo wizard.

## Testes (1)
- `tests/test_politica_externa_release.py` — 9 verificações estáticas; **não** comprova bloqueio em chamada SIP real.

## Documentação (6)
- `docs/politica-internacional-homologacao.md` — instruções e limites da homologação.
- `docs/release-fechamento-20-entregas.md` — critérios REL-01 a REL-20.
- `docs/roadmap-100-funcionalidades-candidatas.md` — candidatos não homologados.
- `docs/roadmap-1000-funcionalidades-auditoria.md` — auditoria e expansão de backlog.
- `docs/campanha-500-testes-release.md` — distribuição dos 500 casos planejados.
- `docs/30-atividades-fechamento-pabx.md` — 30 atividades e critérios de aceite.

**Total inventariado: 10 arquivos (3 código/configuração, 1 teste, 6 documentação).**

## Commits identificados
- `467ebe04` — política na rota alternativa.
- `91861f02` — política no wizard.
- `e9c2feec` — inicialização fail-closed.
- `1e497425` — regressões estáticas adicionais.
- `d23bec8c` — plano dos 500 testes.
- `334c7d74` — 30 atividades de fechamento.

**Observação:** a relação acima identifica commits relevantes, não substitui o histórico completo da PR. O inventário de arquivos é completo segundo a listagem paginada da PR na data-base.

## Riscos abertos
- Falta teste de discagem internacional em Asterisk real para rota principal, alternativa e tenant dinâmico.
- CI do commit mais recente deve concluir antes do aceite REL-19.
- Backup, restauração e rollback não homologados.
- Não liberar release candidate nem implantação em produção por este inventário.
