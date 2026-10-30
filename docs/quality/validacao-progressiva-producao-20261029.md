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

## Política para próximas integrações

- **Código em `main`**: merge apenas com todos os checks disponíveis para o HEAD da PR aprovados.
- **Release candidate**: congelar SHA, registrar matriz de CI/lab, configurar segredos/TLS de destino e executar `scripts/verify_deployment.py` no host correto.
- **Produção**: exige execução/aceite humano das 15 provas, plano de rollback e GO explícito; não pode ser inferida da CI ou deste documento.
- O presente documento **não** altera indicadores, executa telefonia real, habilita deployment ou autoriza GO.
