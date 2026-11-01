# AXE PABX — pacote local de homologacao da release candidate

Escopo: **PABX puro**, sem Contact Center/IA. Este roteiro organiza as **13
homologacoes** e as **15 provas operacionais** para revisao posterior.
Nenhum comando aqui inicializa Asterisk, abre chamadas, toca Docker, altera
producao ou autoriza GO.

## Criar um pacote privado de trabalho

Use um SHA de 40 caracteres do codigo que sera realmente implantado em
**laboratorio controlado**. O SHA abaixo corresponde a tag de engenharia
v0.1.0-rc.1, e nao ao HEAD posterior da main.

```bash
python3 scripts/rc_evidence_packet.py --sha 3496a5f6e168c95fe3c68e20c8cc45bceb3eb5c9 \
  --init /tmp/axe-pabx-rc-evidencias.json
```

O comando cria arquivo novo com permissao 0600 e falha se ja existir.
Nao versionar arquivos preenchidos no GitHub nem incluir dados de clientes,
SIP, PIN, senhas, tokens, telefones, gravacoes ou logs brutos.

O arquivo nasce com 13 cenarios e 15 provas em estado `pending`. Cada
registro aceita `pending`, `failed`, `blocked` ou `passed`.
O campo `evidence` e somente um **identificador opaco**, por exemplo
`EV-LAB-20261101-001`; deve apontar para evidencias custodidas e revisadas
fora do Git. Marcar `passed` nao atesta que o teste ocorreu.

Para cada cenario e prova e necessario executar os testes apropriados em
ambiente seguro e documentar SHA efetivo, data, responsavel, resultado e
evidencia sanitizada em um sistema externo de auditoria. Este script nao
recolhe nem autentica esses dados.

## Consultar cobertura declarada

```bash
python3 scripts/rc_evidence_packet.py --sha 3496a5f6e168c95fe3c68e20c8cc45bceb3eb5c9 \
  --evaluate /tmp/axe-pabx-rc-evidencias.json
```

Codigos de saida:

- `0` no modo `--init`: arquivo criado (nenhum teste executado).
- `0` no modo `--evaluate`: 13 + 15 declarados como passed, **somente apto a revisao independente**.
- `1` no modo `--evaluate`: existem pendencias ou falhas, **NO-GO**.
- `2`: pacote malformado/inseguro ou SHA divergente, **NO-GO**.

O relatório mostra apenas totais, percentuais declarados, SHA informado,
marcadores de verificacao **false** e `operational_go_authorized=false`.
Mesmo o resultado 28/28 nao autoriza deploy nem comprova evidencias.
As tarefas pendentes continuam em
`docs/quality/provas-operacionais-diferidas.json`;
o modelo original `docs/modelo-homologacao-pabx.json` permanece intacto.

## Para revisao humana, antes de producao

1. Confirmar codigo/tags de cada instancia, controles de acesso e inventario do ambiente-alvo.
2. Realizar verificacoes reais de SIP/TLS, registros, RTP/SRTP, DIDs, isolamentos, URA, transferencia, gravacao, backup/restauracao, failover e demais provas especificadas.
3. Conferir autenticidade, integridade, aprovador e vinculo de cada evidencia ao mesmo SHA.
4. Aprovar formalmente seguranca, plano de rollback, janelas e GO em uma etapa separada.

Relacionados: `scripts/homologation_gate.py`,
`scripts/release_evidence.py`,
`docs/releases/rc-0.1.0-rc.1-checklist.md` e issue #173.

**Estado inicial: 0/13 e 0/15; producao NO-GO.**
