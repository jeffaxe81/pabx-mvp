# Manual 112 — Pickup dirigido restrito à empresa (marco 8 parcial)

## Risco corrigido

A rota `POST /api/queue/pickup` verificava se a extensão de destino estava
na allowlist, mas podia tentar redirecionar pelo AMI uma chamada que aguardava
em fila de outra empresa. **A allowlist de ramais sozinha não prova a origem
da chamada**.

## Limite implementado

Antes de executar `redirect_channel`, a API consulta `QueueStateTracker`
para encontrar a fila do canal registrado por `QueueCallerJoin` (AMI). O
JSON do solicitante não determina a fila. O identificador exato do tenant
do ramal precisa coincidir com o da fila `fila-tN`, `fila-tN-en` ou
`fila-tN-es`.

Um canal ausente, removido, em fila desconhecida ou de outra empresa resulta
em HTTP 403 sem chamar o AMI. A checagem rejeita colisões de prefixos como
`t1` versus `t10` e mantém o caminho legítimo para ramais permitidos e
filas da mesma empresa.

## Evidências automatizadas

`queue-api/tests/test_pickup_tenant_boundary.py` executa solicitações HTTP
reais em loopback com AMI simulado. Verifica negativas, ausência de
`redirect_channel`, casos positivos, cancelamento de fila e requisições
com nome de fila falsificado. É teste de API local, **não** valida chamada
física ou runtime AMI/Asterisk em infraestrutura operacional.

## Limites e pendências obrigatórias

- A rota HTTP ainda não autentica a identidade do solicitante.
  O campo `extension` vindo do cliente pode ser falsificado. Este gate
  **não** substitui sessão autenticada, credencial por tenant e controle
  de acesso por papel. Acesso à API deve permanecer restrito na rede/proxy.
- `GET /api/queue` e outras rotas herdadas ainda precisam de revisão
  de visibilidade entre tenants antes de disponibilizar acesso direto.
- Uma chamada pode mudar de fila entre o evento AMI e o comando de
  redirecionamento. O aceite completo exige teste de concorrência com
  confirmação no Asterisk e proteção de identidade ponta a ponta.
- Sem deploy, merge automático, GO, aceite de Marco 8 ou avanço da
  contagem 7/16 com base neste incremento.

## Regressão

```bash
cd queue-api
python3 -m pytest -q tests/test_pickup_tenant_boundary.py tests/test_pickup.py
```

A CI estática e o laboratório Asterisk da revisão do PR precisam concluir
antes do aceite de código. O ambiente real do cliente continua pendente.


## Correção 31/10/2026 — frente 4/10

Validar allowlist tipada e canais do pickup. A API preserva o contrato de respostas válidas e recusa entradas ambíguas. Testes negativos adicionados na suíte do serviço. Homologação operacional e produção continuam pendentes.
