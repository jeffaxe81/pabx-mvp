# AXE PABX — duas métricas diferentes e auditáveis

**Data-base: 29/10/2026.** Esta matriz não substitui o aceite operacional.

## 1. Percentual formal de homologação — 43,8%

O programa de 16 semanas em `docs/plano-16-semanas-pabx.json` registra **7 marcos com status `done`**. A conta oficial continua `7 / 16 = 43,75% ≈ 43,8%`. Os marcos 8 e 9 continuam `in_progress`, e `operational_go_authorized=false`.

Não é correto mover um marco inteiro para `done` apenas por possuir PRs ou CI aprovada em partes.

## 2. Avanço técnico ponderado por critérios — 51,3%

A medição complementar de engenharia usa um denominador de **16 marcos equivalentes**. Cada marco já `done` vale uma unidade. Para um marco `in_progress`, cada critério específico verificado em laboratório conta a mesma fração do marco; o resto permanece pendente.

| Marco | Critérios observados em laboratório | Critérios ainda pendentes | Fração técnica |
| --- | --- | --- | ---: |
| 1–7 | Sete marcos concluídos no plano formal | — | 7,0 |
| 8 — isolamento multiempresa | SIP/ramais, DID, filas | PIN real/caixa postal, gravações e volumes reais | 3/5 = 0,6 |
| 9 — contact center | Entrada na fila, espera contínua e transbordo no laboratório descartável | Callback ponta a ponta e SLA real | 3/5 = 0,6 |
| 10–16 | — | Marcos ainda não concluídos | 0,0 |

**Fórmula:** `(7 + 3/5 + 3/5) / 16 × 100 = 51,25%`, arredondado para **51,3%**.

Esses 51,3% representam **critérios técnicos parcialmente exercitados**, não 50% de homologação formal e definitivamente não 50% de prontidão para produção. Esta fração não é uma previsão de esforço ou tempo restante.

## Como conferir

```bash
python3 scripts/project_progress.py
python3 -m pytest -q scripts/tests/test_project_progress.py
python3 -m lab.asterisk_lab --calls --queues --report lab-results/queue-tenants.json
```

O registro granular está em `docs/quality/progresso-tecnico-criterios.json`, com caminho de implementação e job de CI para cada critério técnico. A evidência de espera exige três medições individuais t1/t2/t3 na aplicação `Queue` por no mínimo um segundo consecutivo. Falhas ou dados ambíguos impedem a aprovação do laboratório.

O script valida integridade estrutural e aponta referências, mas **não autentica sozinho o estado remoto do GitHub Actions**; só publicar como resultado aprovado quando as suítes da PR na cabeça SHA forem concluídas com sucesso. O laboratório é descartável, não a instalação operacional.

## Provas operacionais diferidas — registro em código

Por orientação de continuidade de desenvolvimento, as provas operacionais
**não executadas** estão registradas em
`docs/quality/provas-operacionais-diferidas.json` (15 pendências de
9 marcos). A validação estática desse cadastro é executável por
`python3 scripts/operational_proofs_deferred.py` e **não** prova
funcionamento em infraestrutura, não altera estados de aceite ou GO.
A CI de código e segurança continua obrigatória para incorporar PRs.

## Próximos requisitos para os 50% formais

Concluir o Marco 8 com a autenticação real por PIN válido/incorreto (e bloqueio de tentativas), acesso a mensagens e gravações reais sem vazamento entre empresas, segregação do armazenamento, autorização/sessão HTTP integrada ao Asterisk, revisão de evidências e aceite responsável. **O GO permanece bloqueado.**
