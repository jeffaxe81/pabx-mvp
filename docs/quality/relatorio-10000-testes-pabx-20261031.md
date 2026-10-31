# Relatório de Testes — AXE PABX puro — 10.000 casos

**Data:** 31/10/2026  
**Repositório:** [jeffaxe81/pabx-mvp](https://github.com/jeffaxe81/pabx-mvp)  
**Lote:** PRs [#299](https://github.com/jeffaxe81/pabx-mvp/pull/299) a [#308](https://github.com/jeffaxe81/pabx-mvp/pull/308)  
**SHA da `main` utilizado na validação consolidada:** `3b163ebb7947b587fc403a117d7cb5fff5a58bf2`  
**Workflow consolidado:** [GitHub Actions #41204897656](https://github.com/jeffaxe81/pabx-mvp/actions/runs/41204897656)

## 1. Resumo executivo

| Indicador | Resultado |
|---|---:|
| Novos casos parametrizados pytest | **10.000 / 10.000** |
| Identificadores de caso únicos | **10.000** (`AXE-00001` até `AXE-10000`) |
| Arquivos de teste novos | **10** |
| Funções pytest parametrizadas novas | **10** |
| Casos por arquivo | **1.000** |
| PRs aprovadas e integradas à `main` | **10 / 10** |
| Checks obrigatórios nas PRs | **160 / 160**, todos concluídos com sucesso |
| Checks da CI consolidada na `main` | **8 / 8**, aprovados |
| Testes pytest na CI consolidada (incluindo base histórica) | **11.168**, aprovados |
| Testes de chamadas reais em operadora/ambiente de produção neste lote | **0** |
| Liberação de produção | **NÃO AUTORIZADA** |

**Interpretação do número 10.000:** são 10.000 **invocações de teste parametrizadas**, com 10.000 IDs e entradas distintas, distribuídas entre dez famílias de invariantes. Não representam 10.000 funcionalidades diferentes, 10.000 chamadas simultâneas, ensaio de carga, certificação de operadora ou homologação de mídia. Os jobs existentes de Asterisk/Chromium na CI são executados adicionalmente, mas não convertem estas 10.000 invocações em ensaios operacionais de campo.

## 2. Matriz de execução, cobertura e resultados

| IDs | Área do PABX | Arquivo | PR | Casos | Checks |
|---|---|---|---|---:|---:|
| 00001–01000 | Normalização de bloqueio de números e rejeição de caracteres ocultos | `admin-api/tests/test_pabx_10000_01.py` | [#299](https://github.com/jeffaxe81/pabx-mvp/pull/299) | 1.000 | 16/16 |
| 01001–02000 | Destinos de discagem direta e rejeição de ramais inválidos | `admin-api/tests/test_pabx_10000_02.py` | [#300](https://github.com/jeffaxe81/pabx-mvp/pull/300) | 1.000 | 16/16 |
| 02001–03000 | Ramais SIP, isolamento multiempresa e colisões de numeração | `admin-api/tests/test_pabx_10000_03.py` | [#301](https://github.com/jeffaxe81/pabx-mvp/pull/301) | 1.000 | 16/16 |
| 03001–04000 | Cadastro de tenants e exclusividade dos DIDs | `admin-api/tests/test_pabx_10000_04.py` | [#302](https://github.com/jeffaxe81/pabx-mvp/pull/302) | 1.000 | 16/16 |
| 04001–05000 | Autenticação TOTP com 1.000 períodos diferentes | `admin-api/tests/test_pabx_10000_05.py` | [#303](https://github.com/jeffaxe81/pabx-mvp/pull/303) | 1.000 | 16/16 |
| 05001–06000 | Formatação AMI, correlação de campos e injeção CRLF | `admin-api/tests/test_pabx_10000_06.py` | [#304](https://github.com/jeffaxe81/pabx-mvp/pull/304) | 1.000 | 16/16 |
| 06001–07000 | PINs de voicemail, numeração de caixas e isolamento | `scripts/tests/test_pabx_10000_07.py` | [#305](https://github.com/jeffaxe81/pabx-mvp/pull/305) | 1.000 | 16/16 |
| 07001–08000 | Evidência CLI simulada do Asterisk e mapeamento AstDB de DID | `scripts/tests/test_pabx_10000_08.py` | [#306](https://github.com/jeffaxe81/pabx-mvp/pull/306) | 1.000 | 16/16 |
| 08001–09000 | Correlação PJSIP/voicemail e detecção de acessos entre empresas | `scripts/tests/test_pabx_10000_09.py` | [#307](https://github.com/jeffaxe81/pabx-mvp/pull/307) | 1.000 | 16/16 |
| 09001–10000 | Retenção e expurgo controlado de backup em diretórios temporários | `backup/tests/test_pabx_10000_10.py` | [#308](https://github.com/jeffaxe81/pabx-mvp/pull/308) | 1.000 | 16/16 |
| **TOTAL** | | | | **10.000** | **160/160** |

Cada bateria contém **500 variantes de um comportamento permitido** e **500 variantes de um comportamento negado/controlado**, incluindo o caso de retenção: 500 arquivos preservados e 500 expurgados sob a política configurada. Os identificadores e as expectativas estão no catálogo completo [`catalogo-10000-testes-pabx-20261031.csv`](catalogo-10000-testes-pabx-20261031.csv).

## 3. Evidência de execução real pelo GitHub Actions

Foi confirmada a execução das dez baterias em jobs `pytest`, além do sucesso de todos os gates de cada PR. No **commit consolidado da `main`**, os jobs de testes reportaram:

| Job consolidado | Resultado pytest | Link direto à execução |
|---|---:|---|
| `pytest | admin-api` | **6.662 passed** | [job 124547882784](https://github.com/jeffaxe81/pabx-mvp/actions/runs/41204897656/job/124547882784) |
| `pytest | scripts` | **3.481 passed** | [job 124547882605](https://github.com/jeffaxe81/pabx-mvp/actions/runs/41204897656/job/124547882605) |
| `pytest | backup` | **1.025 passed** | [job 124547882858](https://github.com/jeffaxe81/pabx-mvp/actions/runs/41204897656/job/124547882858) |
| **TOTAL** | **11.168 passed** | [workflow](https://github.com/jeffaxe81/pabx-mvp/actions/runs/41204897656) |

A diferença entre 11.168 testes do total consolidado e 10.000 casos novos corresponde aos **1.168 testes já existentes** nas três suítes. As 10.000 novas invocações são 6.000 no `admin-api`, 3.000 em `scripts` e 1.000 em `backup`.

**Evidências dos jobs das PRs:** as seis primeiras PRs registraram **1.662 passed** no `admin-api`; as três PRs de scripts registraram **1.481 passed** no respectivo job; a PR de backup registrou **1.025 passed**. Cada conjunto de checks da PR passou em **16/16**. Não somar esses números repetidamente: os trabalhos de CI individuais executam novamente os testes antigos.

## 4. Catálogo completo, rastreabilidade e modo de geração

Arquivo detalhado: [**Catálogo CSV de 10.000 casos**](catalogo-10000-testes-pabx-20261031.csv).

Cada linha contém:
- `case_id`: identificador global `AXE-00001`–`AXE-10000`;
- `grupo` e `pr`: módulo e PR original;
- `indice_no_grupo`: valor de parametrização de 0 a 999;
- `cenario_esperado`: comportamento esperado conforme a classe do caso;
- `arquivo_teste`: fonte executável do teste;
- `resultado_ci`: `APROVADO_NA_SUITE` significa que o job pytest da respectiva suíte foi aprovado. Não substitui um log separado por ID individual nem uma prova física.

Os casos são determinísticos, exceto os segredos gerados internamente pelo validador de ramais. Para reproduzir localmente é necessário utilizar as mesmas dependências e o ambiente de teste descritos no workflow do repositório. A prova da execução conjunta se apoia nos três jobs consolidados ligados acima.

## 5. Não conformidades, correções e limites

**Neste lote:** não houve falha persistente nos dez arquivos após a execução consolidada. As dez PRs foram aprovadas e integradas, sem relaxamento dos 16 checks. Não houve implantação em produção.

**Pendências já conhecidas e não resolvidas por estes 10.000 casos:**
1. [#61](https://github.com/jeffaxe81/pabx-mvp/issues/61) — instabilidade histórica de negociação WebRTC/DTLS/SRTP e mídia em laboratório, que requer investigação de estabilidade.
2. [#88](https://github.com/jeffaxe81/pabx-mvp/issues/88) — prova operacional de PIN digitado e proteção real de voicemail.
3. [#283](https://github.com/jeffaxe81/pabx-mvp/pull/283) — PR anterior de preflight SIP ainda bloqueada pelo gate WebRTC; não foi integrada neste lote.
4. [#173](https://github.com/jeffaxe81/pabx-mvp/issues/173) — homologação operacional exigida para autorização de produção; permanece **NO-GO**.
5. [#276](https://github.com/jeffaxe81/pabx-mvp/issues/276) — Contact Center e IA permanecem no backlog, sem novas entregas relacionadas nesta rodada.

## 6. Conclusão

**Aprovado:** 10.000/10.000 casos automatizados, 10/10 PRs integradas, 160/160 checks individuais verdes e 8/8 checks consolidados na `main`. Catálogo completo versionado ao lado deste documento.

**Não aprovado / não comprovado:** homologação de ambiente produtivo, ligação por operadora real, 10.000 chamadas simultâneas, carga, alta disponibilidade, recuperação física e aceite operacional. **Produção continua NÃO autorizada.**
