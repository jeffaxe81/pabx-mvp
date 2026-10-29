# AXE PABX — Cancelamento seguro de callback pendente (marco 9)

## Objetivo
Permitir que um supervisor ou administrador cancele um pedido de retorno
**antes da reserva para discagem**, sem apagar seu histórico e sem interferir
com chamadas já originadas pelo Asterisk.

## API
`POST /api/callbacks/{id}/cancel`

O ID deve ser hexadecimal minúsculo de 12 caracteres, emitido na criação
do pedido. Requer Bearer da fila para o tenant proprietário, papel
`supervisor` ou `admin`, e cabeçalho `X-Click-To-Call-Key`.
O acesso via navegador também exige origem CORS explicitamente permitida.

Resultados:
- `200` com `{"ok":true,"id":"...","status":"cancelado"}` se o pedido
  estava `pendente` e pertence à empresa autenticada.
- `404` se não existe ou pertence a outra empresa, sem revelar sua
  existência.
- `409` quando o callback já está reservado (`discando`) ou finalizado;
  **não** cancela a chamada real no AMI.
- `503` quando o catálogo persistido está inválido ou indisponível,
  sem sobrescrevê-lo.
- `401` ou `403` para identidade, papel, origem ou chave inválidos.

## Segurança e concorrência
A operação inteira lê e atualiza o catálogo sob o mesmo
`outbound_lock(CALLBACKS_PATH)` usado na seleção, reserva e Originate.
Somente a transição `pendente → cancelado` é aceita.
O histórico mantém telefone, tenant e identificador existentes e
acrescenta `cancelled_at`. O envio de Originate não é chamado nesse
endpoint; um segundo cancelamento responde `409`.

## Validação e limite
Cobertura por testes unitários e HTTP loopback com AMI sintético:
autenticação dupla, isolamento entre empresas, corrida com reserva
já efetivada, rejeição de caminhos inesperados e catálogo corrupto.
Os testes operacionais externos continuam expressamente registrados
como `DEFERRED_NOT_EXECUTED` em
`docs/quality/provas-operacionais-diferidas.json`.
Esta entrega não conclui o marco 9 e não autoriza produção.
