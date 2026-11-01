# AXE PABX — Release Candidate LOCAL 0.1.0-rc.1

**Data-base:** 2026-11-01. **Escopo:** PABX puro; Contact Center e IA fora da candidata.

**Classificação:** candidato de engenharia, **NO-GO operacional**. Nenhum serviço, telefone físico, gateway de operadora ou host de cliente será modificado por esta entrega.

## Identidade e rastreabilidade

- Versão: `VERSION` = `0.1.0-rc.1`.
- Manifesto: `docs/releases/axe-pabx-0.1.0-rc.1.json`.
- Baseline anterior: `0e8ee6d2bff7a3a3ff49fd695560fa80d86144c8` (último 19/20 integrado na main).
- **SHA efetivo do pacote:** commit de integração desta PR em `main`; não presumir o SHA do branch ou da prévia PR.
- **Git tag:** `v0.1.0-rc.1`, criada por workflow complementar `.github/workflows/rel20-rc-tag.yml` após CI e merge na `main`, vinculada ao SHA de integração desse complemento. A criação e o SHA remoto só são considerados confirmados após a execução do workflow. O RC continua NO-GO operacional.
- **Artefato de laboratório:** workflow `REL-20 | pacote RC local` gera `tar.gz` com o conteúdo da revisão e arquivo `SHA256SUMS`. O download é uma cópia do repositório versionado, não instalador validado em host real.

## Checklist de engenharia do RC

- [x] REL-01..REL-19: marcos já aprovados no limite de suas evidências e integrados à `main`.
- [x] REL-13: SIP REFER t1/t2 com aceitação e INVITE/ACK no receptor, PR #356 (174/174 checks no laboratório).
- [x] REL-14: roteamento de troncos em simuladores no loopback, PR #352 (34/34 checks).
- [x] REL-20: versão, manifesto, checklist e verificador fail-closed adicionados.
- [x] CI da PR #358: 22/22 verificações SUCCESS no head integrado ao fechamento inicial.
- [x] SHA do pacote após merge confirmado no GitHub Actions: `3496a5f6e168c95fe3c68e20c8cc45bceb3eb5c9`, workflow `41338933536`, artefato `13096990316` (retido até 2026-11-15). O workflow conferiu `SHA256SUMS`; a execução em GitHub Actions não substitui verificação independente após baixar o arquivo.
- [ ] Realizar homologação operacional no ambiente-alvo, com responsável técnico, credenciais seguras, equipamentos de laboratório e operadora.
- [ ] Completar os 13 cenários do modelo `docs/modelo-homologacao-pabx.json` com evidências independentes e mesmo SHA.
- [ ] Concluir as 15 provas diferidas de `docs/quality/provas-operacionais-diferidas.json`.
- [ ] Obter aprovação humana de GO e plano de reversão antes de qualquer produção.

## Validar o RC em cópia local segura

```bash
python3 scripts/rel20_rc_gate.py
python3 -m pytest -q scripts/tests/test_rel20_rc_gate.py tests/test_rel20_release_100.py
git rev-parse HEAD
git status --porcelain
```

Para validar a integridade do pacote obtido pela CI: `sha256sum -c SHA256SUMS` no diretório onde está o `tar.gz`.

**Bloqueio de produção:** o RC é apto apenas à **revisão técnica local**. Testes de SIP em simuladores não provam interoperabilidade com operador/telefones reais, media pós-transferência assistida, disponibilidade, backup de dados operacionais, segurança do ambiente ou aceite final. O código contém configurações de exemplo que não devem ser implantadas sem preparação e auditoria operacional.

## Complemento de versionamento Git

O pacote RC original foi fechado em PR #358, sem tag. O complemento habilita o workflow de tag anotada `v0.1.0-rc.1`, somente no SHA do merge à `main`, e cria registro GitHub em modo *draft* e *prerelease*. A anotação da tag e o rascunho **não alteram o estado de GO operacional**, não executam deploy nem validam operadoras ou dispositivos físicos.


## Evidência pós-merge verificada — 2026-11-01

- **Tag Git anotada:** `v0.1.0-rc.1`, apontando para `3496a5f6e168c95fe3c68e20c8cc45bceb3eb5c9`; confirmada por objeto Git do tipo `tag` com alvo do tipo `commit`.
- **CI da main no mesmo SHA:** `41338933528` (estática, SUCCESS), `41338933536` (pacote RC, SUCCESS) e `41338933447` (tag, SUCCESS).
- **Pacote RC:** artefato GitHub Actions `13096990316`, associado ao mesmo SHA da tag; expiração prevista 2026-11-15; publicação no workflow de laboratório, **não** instalador homologado.
- **GitHub Release:** `v0.1.0-rc.1` registrada como **draft=true** e **prerelease=true**. Não publicada como GA.
- **Rastreio operacional:** [issue #173](https://github.com/jeffaxe81/pabx-mvp/issues/173), [issue #30](https://github.com/jeffaxe81/pabx-mvp/issues/30) e [issue #88](https://github.com/jeffaxe81/pabx-mvp/issues/88).

## Próximo gate: homologação operacional, não parte do aceite de engenharia

O arquivo `docs/modelo-homologacao-pabx.json` permanece com **13/13 cenários PENDING**, sem evidência de execução e sem SHA homologado. As **15/15 provas operacionais** em `docs/quality/provas-operacionais-diferidas.json` permanecem `DEFERRED_NOT_EXECUTED`. Não atribuir êxito por analogia à CI de laboratório.

Para efetuar testes no ambiente-alvo será necessário identificar responsáveis e infraestrutura de homologação, registrar o **mesmo SHA** avaliado, coletar evidência sanitizada de SIP/TLS, registros, áudio bidirecional, SRTP, DIDs, isolamento de empresas, URA/filas, transferência assistida, gravações, backup/restauração e failover, além de verificar segurança de identidade e credenciais. Antes de cada operação com efeitos no ambiente, manter backup, pré-checagem e plano de reversão. O GO exige revisão humana independente.

**Produção: NO-GO. Nenhuma alteração nesta documentação modifica o commit da tag nem autoriza implantação.**
