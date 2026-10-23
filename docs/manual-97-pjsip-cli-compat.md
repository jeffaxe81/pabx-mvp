# Manual 97 — Compatibilidade da auditoria PJSIP com saída real do CLI

## Problema

O Manual 96 introduziu a consulta `pjsip show endpoint <nome>`, mas
o validador procurava apenas linhas do tipo `Context: t1-internal`.
A saída de versões usuais do Asterisk inclui a opção de configuração
como `context : t1-internal`, com espaços ao redor do separador e
às vezes em minúsculas. Assim, um contexto configurado corretamente
poderia ser reportado como ausente.

## Correção

A auditoria aceita variações de maiúsculas/minúsculas e espaçamento
do campo `context`, mantendo a comparação exata do contexto por
tenant. Também verifica o identificador da linha `Endpoint:`.
Mencionar `t1-internal` em um comentário, diagnóstico ou outro campo
não substitui a opção de contexto.

Os testes usam fixtures similares aos exemplos de saída CLI do
Asterisk e casos negativos de contexto cruzado e prefixo parecido.

## Executar

```bash
(cd scripts && python3 -m pytest -q \
  tests/test_asterisk_cli_realistic.py tests/test_asterisk_lab_audit.py)

python3 scripts/asterisk_lab_audit.py --runtime docker --container pabx-mvp
```

O primeiro comando é automatizado e utiliza respostas simuladas.
O segundo **consulta um Asterisk em execução**, somente quando
o operador o executar num laboratório autorizado. O resultado da
auditoria ainda não prova registro SIP, mídia, chamadas nem
isolamento entre conversas; para isso há o Manual 73.

## Referências técnicas

Documentação Asterisk: `pjsip show endpoint <nome>` para inspecionar
atributos de endpoint e `dialplan show <contexto>` para confirmar
contextos carregados. Exemplos variam entre versões; validar sempre
as saídas da versão concreta instalada.
