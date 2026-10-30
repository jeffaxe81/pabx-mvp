# AXE PABX — Proteção do painel em troca de empresa

## Problema corrigido
O painel operacional exibia o último snapshot de filas/SLA/ramais mesmo
depois de a credencial Bearer ser removida, trocada por outra empresa,
ou revogada. O polling também podia retornar de forma invertida: uma
resposta lenta de `t1` poderia ser renderizada após o usuário informar
uma credencial de `t2`.

## Solução
- Um evento `input` em `queueToken` invalida imediatamente todas as
  respostas pendentes, limpa **oito** áreas de dados protegidas e
  remove a marca de atualização anterior.
- Cada ciclo de polling captura a credencial e uma geração monotônica
  `requestGeneration`. Uma resposta só pode ser renderizada se a
  geração e a credencial ainda forem exatamente as mesmas.
- As oito consultas do ciclo usam a mesma credencial capturada, evitando
  mistura de dados quando há edição do campo.
- Se alguma das fontes do ciclo falhar/rejeitar autenticação, o painel
  falha fechado: oculta o snapshot anterior e informa indisponibilidade.
  Nenhuma leitura antiga fica apresentada como se fosse atual.
- O botão **Atualizar fila** utiliza o mesmo mecanismo de atualização
  protegida, sem rota paralela que contorne o isolamento.
- `Bearer` permanece exclusivamente em cabeçalho HTTP. O token não é
  gravado em `localStorage`, `sessionStorage` ou URL.

## Regressão
Teste de Chromium com APIs sintéticas e duas empresas: primeira consulta
`t1`, troca para `t2`, resposta atrasada de `t1` e revogação de
`t2`. Verifica que não há exibição residual de informações de outra
empresa e que o painel avisa a indisponibilidade.

As 15 provas operacionais externas permanecem deferidas; esta melhoria
não constitui homologação de produção nem autoriza GO.
