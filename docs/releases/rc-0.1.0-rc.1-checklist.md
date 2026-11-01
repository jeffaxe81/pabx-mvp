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
- [ ] Confirmar o SHA integrado no artefato gerado após o merge.
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
