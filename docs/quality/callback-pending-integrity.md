# Marco 9 — Callback pendente inválido não significa fila vazia

A `queue-api` responde a `POST /api/callbacks/dial-next` com
`{"done": true}` apenas quando não existe pedido pendente válido.
Um pedido corrompido não pode ser interpretado como "não há chamadas":
isso ocultaria um retorno devido ao cliente e permitiria que o
sistema continuasse sem corrigir a persistência.

## Mudança

A leitura de `callbacks.json` valida todos os pedidos com
`status: pendente`, antes de filtrar pela empresa que fez a
requisição. Confere número canônico, data finita não negativa,
contador inteiro de tentativas em faixa aceitável e identificação
válida de tenant quando presente.

Se um pedido pendente do `t10` estiver inválido, o arquivo é
considerado indisponível também para a seleção do `t1`: a regra
é falhar fechado, sem alterar o arquivo nem enviar ação AMI.
A listagem e a tentativa de discagem retornam `503` genérico,
sem declarar conclusão ou fila vazia.

Pedidos concluídos e históricos legados continuam legíveis,
desde que possuam IDs únicos. Registros antigos sem informação
de tenant continuam possíveis, mas não são selecionados por uma
requisição autenticada de um tenant.

## Escopo e restrições

A mudança usa testes de código e HTTP local. Não realiza
chamada/DTMF em ambiente de cliente. As provas operacionais
permanecem `DEFERRED_NOT_EXECUTED` no registro versionado;
os marcos 8/9 continuam em andamento e o GO não é autorizado.
