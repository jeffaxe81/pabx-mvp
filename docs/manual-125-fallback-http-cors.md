# Manual 125 — Rotas HTTP desconhecidas sem CORS amplo

## Problema corrigido

A `queue-api` protege as rotas de fila, métricas, campanhas e gravações
com autenticação e CORS por origem permitida, mas a resposta genérica
para endpoints inexistentes ainda adicionava
`Access-Control-Allow-Origin: *`. Além disso, qualquer solicitação
`OPTIONS` desconhecida retornava 204 (aceita), mesmo sem uma rota
correspondente. Esse fallback permissivo criava risco de regressão se
uma rota nova viesse a usar a resposta genérica por engano.

## Comportamento após a alteração

- Rotas **não cadastradas**: GET, POST, DELETE e OPTIONS retornam
  `404`, sem cabeçalhos CORS e sem detalhe interno.
- Respostas genéricas incluem `Cache-Control: no-store` e
  `X-Content-Type-Options: nosniff`.
- Rotas **conhecidas** mantêm as regras existentes de Bearer,
  autenticação por tenant, CORS explícito e preflight autorizado.
- Nenhum novo serviço, segredo, porta ou dependência foi adicionado.
- A alteração não autoriza GO nem substitui a homologação real de
  Asterisk, WebRTC, callbacks ou gravações.

## Verificação

```bash
cd queue-api
python3 -m pytest -q tests/test_unknown_http_cors.py
```

O teste abre a API somente no endereço local efêmero, sem acesso à
telefonia. Verifica quatro métodos, duas rotas desconhecidas, ausência
de wildcard, resposta 404 e preflight normal de rota protegida.
O restante da suíte `queue-api` deve continuar aprovado na CI antes
de merge.

## Próximo gate

Retomar o aceite da PR #76 com **AMI e Asterisk reais**: comprovar que
`OriginateResponse.Uniqueid` corresponde ao `ChannelId` originado e
estudar o vínculo conservador com `DialEnd` em chamadas de campanhas
e callbacks. Nenhuma inferência por número de destino deve ser
utilizada como prova de atendimento.
