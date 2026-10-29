# Marco 9 — Leitura conservadora do catálogo de callbacks

## Situação tratada

O serviço `queue-api` persiste os callbacks em JSON. Um arquivo
externamente alterado com identificadores repetidos, objetos com
chaves duplicadas ou valores não finitos pode ser interpretado de
maneiras diferentes por leitores distintos. Retornar uma lista vazia
nesses casos ocultaria pedidos e poderia provocar discagens indevidas.

## Implementação

- `load_callbacks` rejeita objetos JSON com **chaves duplicadas em qualquer nível**,
  valores `NaN`, `Infinity`, `-Infinity`, catálogos que não são listas,
  registros com IDs inválidos/duplicados e caminhos de arquivo simbólicos.
- Apenas **arquivo ausente** é interpretado como catálogo inicialmente vazio.
  Arquivo existente e inválido nunca é zerado ou regravado automaticamente.
- `GET /api/callbacks` e `POST /api/callbacks/dial-next` respondem
  `503` com erro genérico, sem revelar dados e sem chamar `AMI Originate`.
- O recebimento de eventos AMI não deve ser derrubado pela corrupção
  do catálogo; desfechos ambíguos e novas solicitações não são persistidos.
- As negativas preservam integralmente os bytes do catálogo para
  investigação e restauração controlada.

## Cobertura de código

Testes unitários e HTTP loopback com JSON malformado, duplicidade de
campos, IDs de empresas distintas, números não finitos e symlinks.
A CI técnica do repositório permanece obrigatória para merge.

## Limites

Não executa nem substitui provas operacionais de callback, URA,
gravação, voicemail ou SLA. As provas externas continuam com
`DEFERRED_NOT_EXECUTED` em
`docs/quality/provas-operacionais-diferidas.json`. Nenhum marco
é homologado por esta correção e não há autorização de produção.
