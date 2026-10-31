# REL-03 — Auditoria inicial de duplicidade do roadmap

Esta matriz registra comparacoes verificaveis com arquivos conhecidos da PR #311.
Nao presume inexistencia no restante do repositorio. Status "PARCIAL" nao e entrega nova.

| Candidato | Evidencia encontrada | Classificacao | Lacuna |
|---|---|---|---|
| AXEF-0011 Bloqueio internacional por tenant | `asterisk/dialplan_politica_externa.conf`, `asterisk/extensions.conf`, `admin-api/tenants.py` | PARCIAL / JA IMPLEMENTADO EM CODIGO | Homologar chamadas SIP reais e persistencia AstDB |
| AXEF-0017 Normalizacao E.164 | `asterisk/extensions.conf` possui remocao de prefixo na rota alternativa | PARCIAL | Nao equivale a normalizacao E.164 completa |
| AXEF-0020 Auditoria de alteracoes de regras | `scripts/verificar-politica-externa.sh` le configuracao | NAO COMPROVADO | Leitura nao e trilha de alteracoes |
| AXEF-0030 Simulacao de roteamento sem chamada | Testes estaticos e preflight de contextos | NAO COMPROVADO | Preflight nao simula decisao de roteamento |
| AXEF-0065 Validacao de contexto de origem | `tests/test_politica_externa_release.py` valida contexto por leitura de arquivo | PARCIAL | Validar origem SIP e isolamento em laboratorio |
| AXEF-0081 Verificacao de integridade do dialplan | `scripts/verificar-politica-externa.sh` consulta contextos | PARCIAL | Sem verificacao periodica nem integridade completa |
| AXEF-0082 Validacao pre-reload | Preflight nao faz reload | PARCIAL | Sem validacao sintatica abrangente do dialplan |
| AXEF-0100 Relatorio de recusas por politica | `NoOp` no contexto de negacao | NAO COMPROVADO | Log de console nao e relatorio estruturado |

## Criterios de fechamento REL-03

- [x] Identificar candidatos potencialmente duplicados com codigo atual.
- [x] Registrar evidencias por caminho e distinguir parcial de concluido.
- [ ] Confrontar todos os 100 candidatos com codigo e documentacao do repositorio.
- [ ] Substituir candidatos duplicados antes de contabilizar novas funcionalidades.
- [ ] Revisar classificacoes com execucao de testes e CI.

**Estado: PARCIAL (8/100 analisados nesta matriz).** Nao contar como release homologada.
