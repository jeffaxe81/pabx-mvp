# Manual 99 — Programa de 16 semanas (quatro meses) do AXE PABX

## Objetivo

Antecipar quatro meses de planejamento e execução em uma sequência
**auditável de 16 marcos semanais**, cada um com critério de aceite.
Esta entrega cria o instrumento de gestão do ciclo; **não equivale
à conclusão antecipada de 16 semanas de implantação e homologação**.

Fonte versionada: `docs/plano-16-semanas-pabx.json`.

## Mês 1 — Laboratório e registros SIP (semanas 1–4)

1. Parser de auditoria PJSIP compatível com formatos reais (**PR #49**).
2. Recuperação do catálogo após falha tardia (**PR #50**).
3. Subir Asterisk Docker em ambiente isolado e registrar versões e
   volumes reais.
4. Validar registro SIP autenticado dos tenants t1, t2 e t3+.

## Mês 2 — Telefonia e segurança multiempresa (semanas 5–8)

5. Chamada interna com estabelecimento, desconexão e CDR.
6. RTP bidirecional e negociação SRTP/DTLS sob TLS.
7. DID conhecido encaminhado corretamente e DID desconhecido negado.
8. Isolamento efetivo entre tenants: URAs, filas, gravações e voicemail.

## Mês 3 — Atendimento e resiliência (semanas 9–12)

9. URA, filas, callback, transbordo e indicadores SLA.
10. Transferência assistida, gravações e permissões.
11. Recuperação de backup de configuração, AstDB e volumes.
12. Testes de interrupção controlada, RTO/RPO e recuperação.

## Mês 4 — Desempenho e GO (semanas 13–16)

13. Auditoria de hardening, TLS, ACL e segredos.
14. Ensaio de carga/estabilidade com recursos mensurados.
15. Release candidate, CI, SHA e evidências dos 13 cenários.
16. Revisão formal GO/NO-GO, contingência e implantação autorizada.

## Relatório de progresso

```bash
python3 scripts/program_progress.py --format markdown

python3 scripts/program_progress.py --format json
```

Para atualizar o avanço, altere apenas o JSON versionado por PR.
Cada marco `done` exige números de PR e de execução CI reais,
verificáveis no GitHub. Não marque um marco como concluído apenas
porque o código foi escrito: o aceite de laboratório deve estar
comprovado para as etapas que exigem testes reais.

O cálculo é `marcos concluídos / 16` (25% por mês quando seus
quatro marcos forem entregues), distinto do avanço das PRs
específicas ou das 13 provas do Manual 73.

Checkpoint de 23/10/2026: o marco 6 foi entregue pela PR #56 e o marco 7
pela PR #57. A CI real 40009695151 e a CI estática 40009694965 também
aprovaram ambos na sequência de integração. O programa está em
**7/16 (43,8%)**. A rodada foi limitada pelo usuário a essas duas semanas
e encerra antes do marco 8. Os aceites e as correções estão no
[Manual 104](manual-104-webrtc-dids-reais.md).

## Condições de GO

Mesmo com o programa em 100%, o script **não autoriza produção**.
O relatório não verifica automaticamente o GitHub e não executa
telefonia, recuperação ou testes reais; somente valida e apresenta
o estado declarado no JSON. Aprovação técnica e operacional exige
revisão humana independente, backups testados, segurança de segredos
e evidências dos 13 cenários do Manual 73.
