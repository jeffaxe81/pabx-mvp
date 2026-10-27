# Manual 114 — Presença, pausa e estado de ramais isolados por empresa

## Alteração de segurança (Marco 8, parcial)

As rotas de operador agora reutilizam o mesmo Bearer e a política privada
de acesso por empresa do Manual 113. Sem token válido ou com origem não
permitida, retornam HTTP 401/403; não herdam CORS wildcard e enviam
`Cache-Control: no-store`.

| Rota | Regra de acesso |
| --- | --- |
| `GET /api/presence` | Somente entradas cujos ramais começam com o tenant autenticado e hífen, como `t1-` |
| `POST /api/presence/<ramal>` | Agente: próprio ramal; supervisor/admin: ramal válido do próprio tenant |
| `DELETE /api/presence/<ramal>` | Mesma regra; não remove estado de outra empresa |
| `POST /api/queue/pause` | Mesmo controle, aplicado **antes** de `AMI.QueuePause` |
| `GET /api/extension-states` | Somente eventos AMI com contexto exato `tN-hints` |
| `GET /api/reports/pauses` | Histórico restringido aos ramais do tenant autenticado, antes da agregação |

Números internos como `1010` podem existir em várias empresas. O
`ExtensionStateTracker` agora usa a chave composta `(contexto, ramal)`,
impedindo que atualização de t2 substitua o estado do mesmo número
em t1. Contexto desconhecido não é exposto na consulta do tenant.

Entradas com tipos errados, textos excessivamente longos ou tamanho
de requisição fora do limite são recusadas antes de alterar arquivo
ou enviar comandos ao Asterisk. O Webphone envia o Bearer apenas
pelo cabeçalho Authorization e exige HTTPS fora de localhost.

## Regressões

```bash
cd queue-api
python3 -m pytest -q tests/test_operator_acl_http.py \
  tests/test_presence.py tests/test_agent_pause.py tests/test_extension_states.py
```

A suíte HTTP usa loopback e AMI simulado: t1/t2, identidade ausente,
autoatendimento, supervisor, entradas hostis e negação de CORS. A suíte
de eventos verifica dois tenants com extensão numérica igual.

## Limites pendentes

- A autenticação é um Bearer local de curta duração, ainda sem integração
  criptográfica com a sessão SIP ou sessão empresarial/SSO.
- As demais rotas HTTP de métricas, SLA, campanhas, callbacks, relatórios
  gerais e presença SIP precisam de gates próprios antes de acesso
  multiempresa amplo. O antigo endpoint de presença só suporta os
  nomes de ramais que carregam o prefixo completo do tenant.
- O módulo AMI ainda requer verificação de chamadas e de troca de
  contexto em ambiente real do cliente.
- Esta entrega não conclui o Marco 8 nem autoriza merge automático,
  deploy ou GO de produção. Programa permanece 7/16.
