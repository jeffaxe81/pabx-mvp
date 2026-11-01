# Evidencias de aceite para REL-04, REL-05 e REL-06

## REL-04 — Politica internacional

- [x] Regra de prefixo 00 implementada em `asterisk/dialplan_politica_externa.conf`.
- [x] Regra por tenant e familia AstDB separada.
- [x] Testes estaticos no repositorio.
- [ ] Discagem SIP real: internacional bloqueada e permitida em t1/t2.
- [ ] Verificacao CDR e dialplan efetivo.

## REL-05 — Rota alternativa

- [x] Rota secundaria aplica politica antes do Dial.
- [x] Verificacao do destino original e revalidacao apos remocao do seletor.
- [ ] Chamadas SIP reais pela rota secundaria, incluindo bloqueio e liberacao.
- [ ] Validar ausencia de bypass por prefixos repetidos e fallback.

## REL-06 — Tenant dinamico

- [x] Wizard gera Set(TENANT), Gosub e tratamento de DENY.
- [x] Testes estaticos de ordem de autorizacao e isolamento adicionados.
- [ ] Executar testes novos na CI especifica.
- [ ] Criar tenant no laboratorio e verificar chamada bloqueada e permitida.
- [ ] Validar rollback do dialplan gerado.

**Importante:** itens marcados em codigo nao representam homologacao SIP real. Nao alterar percentual de release ate concluir o criterio de aceite aplicavel.
