# AXE PABX — validação incremental e condições para produção

Data-base: 2026-10-29 (America/Sao_Paulo).

## Resultado confirmado antes deste registro

- Base inicialmente verificada: `487598cd460434c72541faeffc7cef8697210a2b`.
- [GitHub Actions, execução 40991677382](https://github.com/jeffaxe81/pabx-mvp/actions/runs/40991677382): validação estática `8/8` aprovada. A tentativa 2 reexecutou `pytest | queue-api` e concluiu com sucesso.
- No momento da inspeção inicial não havia pull requests abertas.
- Um laboratório SIP/Asterisk de CI opera em ambiente **descartável**, não em servidor de produção.
- A aprovação de CI **não** implica aprovação de produção.

## Sequência de avaliação dos recursos — um por vez

| Ordem | Componente / evidência | Situação | Próximo bloqueio |
| --- | --- | --- | --- |
| 1 | Configurações e web | CI aprovada | Certificados reais, navegador/WSS no domínio de destino |
| 2 | Administração e credenciais | CI aprovada | Testar autenticação real, roles e revogação |
| 3 | Fila e supervisão | CI aprovada | URA/fila/callback/SLA reais por empresa |
| 4 | IA / transcrição | CI aprovada (mocks) | Homologar modelos, desempenho e privacidade no hardware-alvo |
| 5 | AGI e scripts do Asterisk | CI aprovada | Chamadas, transferências e DTMF SIP reais |
| 6 | Backup e scripts de infraestrutura | CI aprovada | Restaurar integralmente e medir RTO/RPO |
| 7 | Laboratório Asterisk descartável | Executar nos checks da PR | Não substitui rede/operadora/infraestrutura-alvo |
| 8 | Gravações, voicemail e multiempresa | Parcial em CI | Provar segregação e acesso a dados reais |
| 9 | Hardening e capacidade | Pendente | Certificados, ACL, segredos, carga e imagem imutável |
| 10 | Go/no-go e implantação | BLOQUEADO | Evidências aprovadas, responsável e rollback comprovado |

## Registro de problemas e dependências

1. `docs/quality/provas-operacionais-diferidas.json` mantém 15 provas operacionais sem execução/aceite.
2. `docs/plano-16-semanas-pabx.json` mantém marcos 8–16 incompletos e `operational_go_authorized=false`.
3. Não há workflow de implantação produtiva nos três workflows GitHub existentes; não presumir sincronização automática de `main` com servidor real.
4. `README.md` alerta sobre certificados self-signed e senhas de exemplo; `docker-compose.yml` utiliza imagem Asterisk com tag `latest`. Certificados/segredos não devem ser versionados.
5. `scripts/verify_deployment.py` está preparado para checagem pós-deploy, mas o código informa que não foi exercitado em ambiente real.
6. O laboratório WebRTC teve falhas históricas intermitentes de DTLS/RTP, conforme [issue #61](https://github.com/jeffaxe81/pabx-mvp/issues/61); nova aprovação deve ser obtida no commit da PR e não ocultar essa pendência.

Rastreabilidade e check-list de aceite: [issue #173](https://github.com/jeffaxe81/pabx-mvp/issues/173).

## Política de aplicação em ambiente real e homologação

**Regra adotada:** recursos desenvolvidos e aprovados na CI podem ser considerados para aplicação em **ambiente real sob homologação controlada**. A falta de uma prova operacional anterior não impede o registro e a integração do código. Onde não houver comprovação, a classificação passa a ser `CODE_REGISTERED_PENDING_REAL_HOMOLOGATION` (**código registrado — homologação real pendente**). Isso **não afirma** que todos os requisitos estão implementados nem que estão homologados.

Há duas decisões distintas:

1. **Aplicar para homologar:** a equipe responsável pode selecionar um build com SHA identificado e aplicar em infraestrutura real de homologação, ou em janela controlada do ambiente-alvo, com preflight, credenciais próprias, proteção aos dados, backup e plano de rollback. A instalação real não é executada por esta documentação.
2. **Aceitar para operação definitiva:** somente depois de registrar provas reais verificáveis, riscos residuais, aprovação operacional e GO explícito. Não alterar `operational_go_authorized=false` ou os marcos formais por mera aprovação de CI.

A denominação histórica `DEVELOPMENT_ONLY_PROOFS_DEFERRED` no registro informa que as **provas não foram executadas naquela mudança**, e não constitui proibição de homologar em ambiente real depois.

### Política para próximas integrações

- **Código em `main`:** merge apenas com CI de código/segurança aprovada no HEAD exato da PR.
- **Sem evidência operacional:** registrar a implementação como *pendente de homologação*, mantendo evidência/execução/aceite como nulos.
- **Release candidate para homologação:** congelar SHA, verificar segredos e TLS no alvo, checar dependências, monitoramento, backup e rollback; executar `scripts/verify_deployment.py` no host real, quando disponível.
- **Uso definitivo em produção:** registrar aceite separado e decisão go/no-go conforme o escopo e os riscos do ambiente real.
- Este documento não comprova uma implantação executada, não muda indicadores e não autoriza GO automático.

