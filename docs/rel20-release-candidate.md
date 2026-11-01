# AXE PABX — termo de fechamento da release candidate local

**Versão:** `v0.1.0-rc.1` — release candidate da modalidade PABX puro.

**Estado de encerramento:** concluído no escopo de desenvolvimento e laboratório automatizado, sujeito à criação efetiva da tag automática na main e à CI aprovada.

**GO operacional: BLOQUEADO.** Sem implantação em produção. Revisão humana obrigatória antes de qualquer tentativa de homologação com infraestrutura real.

## Aceite técnico (REL-01 a REL-20)

- Inventário, escopo PABX puro, exclusão de Contact Center e IA desta release: REL-01/02.
- Política internacional, isolamento e bloqueios por empresa, geração de tenants e auditoria: REL-04 a REL-12.
- Telefonia TLS/SRTP, CDR, transferências REFER no laboratório: REL-13, PR #356 e PR #357. A renegociação de áudio após REFER e transferência assistida não foram homologadas.
- Troncos principal/alternativo: REL-14, PR #352, dois simuladores UDP em loopback. Não há comprovação de interoperabilidade com operadora ou gateway real.
- Provisionamento, backup e rollback de volumes sintéticos: REL-15/16/17, exclusivamente em sandbox.
- Preflight de segurança e CI geral: REL-18/19. Segredos, certificados e firewall efetivos do host de produção não foram validados aqui.
- **REL-20:** fechamento técnico local, `RELEASE_VERSION`, checklist 20/20, validação `scripts/rel20_release_candidate.py`, tag automática na main após merge e aprovação da CI.

## Procedimento de versionamento e evidência

1. Aprovar todos os checks da PR da REL-20 e realizar merge na branch `main`.
2. O workflow `.github/workflows/rel20-rc-tag.yml` executa preflight no commit da `main`, recusa tag incompatível ou já existente em outro SHA e cria a tag anotada `v0.1.0-rc.1` somente para esse commit.
3. Conferir o SHA associado à tag, o checklist no mesmo commit e a execução do workflow no GitHub. Sem tag confirmada, não anunciar fechamento de RC.
4. Manter o pacote como **release candidate local**: não realizar deploy, não promover para `latest` nem publicar release GA.

## Pendências fora do escopo de aceite local

- Homologação de telefonia com troncos de operadoras e aparelhos físicos; áudio pós-REFER, transferências assistidas e falhas de conectividade.
- Testes com dados operacionais, gestão de segredos, certificados de produção, RTO/RPO e disponibilidade.
- Aprovação do responsável técnico e mudança controlada antes de produção.

**Resultado permitido:** 100% dos 20 critérios delimitados para a RC local. **Resultado proibido:** afirmar prontidão operacional ou liberação produtiva.
