# Manual 106 — Isolamento multiempresa: gate estático inicial (marco 8)

## Situação
O programa permanece em **7/16 marcos aceitos (43,8%)**. Este incremento
abre o marco 8, mas **não o conclui**. O objetivo de aceite ainda exige
provas em Asterisk real de isolamento de ramais, filas, correio de voz,
gravações e DIDs, com controles negativos e trilhas independentes.

## Entrega
`scripts/tenant_isolation_static.py` verifica as quatro configurações
base versionadas (`pjsip.conf`, `extensions.conf`, `queues.conf`,
`voicemail.conf`) sem iniciar serviços nem realizar chamadas.

- Identifica os tenants t1/t2, e outros encontrados nas configurações-base.
- Confere contextos PJSIP, SUBSCRIBE/BLF, vínculo auth/AOR e caixas
  de mensagens.
- Rejeita membros de filas apontando para endpoint de outro tenant.
- Rejeita caixas de voicemail atribuídas a contexto de outra empresa.
- Rejeita referências **literais** a empresa estrangeira em dialplan
  (`PJSIP/tN-`, `@tN`, `fila-tN`, `Goto(tN-internal`,
  `CDR(accountcode)=tN`).
- Se faltam arquivos, há symlink, arquivo grande ou seção crítica
  ausente, retorna falha, nunca um aceite presumido.
- Publica somente IDs de verificações e booleanos/contagens, não
  configuração bruta, senha SIP/PIN, DIDs nem gravações.

## Comandos
```bash
python3 scripts/tenant_isolation_static.py
cd scripts && python3 -m pytest -q tests/test_tenant_isolation_static.py
```

Os testes de regressão incluem referências cruzadas simuladas em
ramais, ACL de contexto, auth, AOR, BLF, voicemail, fila e dialplan;
ausência de arquivos e ataques por symlink; verificação de relatório
sem segredos.

## Limites críticos
**NÃO VERIFICADOS:** includes gerados por tenant/wizard e AstDB, APIs
administrativas/operacionais, autenticação/ACL efetivas, chamadas SIP,
RTP/SRTP, conferência, voicemail efetivo, caminhos de gravações,
DIDs em runtime ou acesso a gravações/arquivos por outro usuário.
A variável dinâmica de dialplan não é expandida pelo scanner.
Validação estática é somente uma barreira; não substitui prova funcional.

O JSON força
`generated_includes_evaluated=false`,
`live_tenant_isolation_tested=false` e
`operational_go_authorized=false`, inclusive em execução bem-sucedida.

## Histórico de problemas e correções
- Risco: cadastro de ramal com contexto de outra empresa. Gate verifica
  `context`, `auth`, `aors`, `subscribe_context` e `mailboxes`.
- Risco: uma fila despachar para endpoint de outro tenant. Gate valida
  todos os membros nas filas-base, inclusive idiomas.
- Risco: plano de discagem criar atalho para tenant estrangeiro.
  Gate recusa referências literais cruzadas conhecidas.
- Lacuna remanescente: includes dinâmicos e acesso via API/AMI não
  estão cobertos. O marco 8 fica aberto até prova negativa real.

## Próximo aceite do marco 8
Executar laboratório descartável com no mínimo t1/t2/t3, tentar
chamada entre empresas e acesso a DID, filas, voicemail e gravações
de empresa estrangeira; comprovar a negação na camada adequada,
ausência de efeitos laterais e CDR/CEL/logs sanitizados. Corrigir falhas
antes de marcar o marco 8 concluído. Sem merge em main ou GO operacional
antes dos gates e revisão.
