# Manual 12 — Discagem por clique a partir do CRM (backlog #6)

## O que é
Um botão "Ligar" na ficha do cliente, dentro do CRM da empresa,
dispara uma ligação sem a telefonista precisar digitar o número. O
fluxo real: o Asterisk **liga primeiro pro ramal da telefonista**;
quando ela atende, o Asterisk **completa a ligação pro número do
cliente** automaticamente.

Isso é diferente de discar pela interface web (manual 06) — aqui quem
inicia é um sistema **externo** (o CRM), não a telefonista digitando.

## Segurança (leia antes de habilitar)
Uma API que origina chamadas é um alvo clássico de fraude de
discagem. Por isso, **vem completamente desligada por padrão**:
- `CLICK_TO_CALL_API_KEY` vazio = toda requisição é rejeitada
- Só ramais na lista `CLICK_TO_CALL_ALLOWED_EXTENSIONS` podem ser
  usados como origem (por padrão, só `t1-recepcao`)
- O número informado é sanitizado (só dígitos, formatação removida) e
  precisa ter pelo menos 8 dígitos, senão a requisição é rejeitada

## Como configurar
No `docker-compose.yml`, serviço `queue-api`:
```yaml
CLICK_TO_CALL_API_KEY: "uma-chave-longa-e-aleatoria-aqui"
CLICK_TO_CALL_ALLOWED_EXTENSIONS: "t1-recepcao"
CLICK_TO_CALL_CONTEXT: "click-to-call"
```

Gere a chave com algo como `openssl rand -hex 32` — não use uma
palavra fácil de adivinhar.

## Como o CRM chama a API

```bash
curl -X POST http://<ip-do-servidor>:8090/api/click-to-call \
  -H "Content-Type: application/json" \
  -H "X-Click-To-Call-Key: uma-chave-longa-e-aleatoria-aqui" \
  -d '{
    "extension": "t1-recepcao",
    "number": "(11) 99999-8888"
  }'
```

Ou em JavaScript (o botão dentro do CRM):
```javascript
async function ligarParaCliente(numeroDoCliente) {
  const response = await fetch('http://<ip-do-servidor>:8090/api/click-to-call', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Click-To-Call-Key': 'uma-chave-longa-e-aleatoria-aqui',
    },
    body: JSON.stringify({
      extension: 't1-recepcao',
      number: numeroDoCliente,
    }),
  });
  const data = await response.json();
  if (!data.ok) {
    console.error('Falha ao ligar:', data.error);
  }
}
```

Resposta de sucesso: `{"ok": true}` (a chamada foi originada — não
significa que já foi atendida, só que o Asterisk começou a discar).
Erros possíveis: `403` (chave errada ou ramal não autorizado), `400`
(número inválido), `503` (queue-api sem conexão com o AMI no momento).

## Como testar manualmente
1. Configure a chave e suba `docker compose up -d`
2. Rode o `curl` de exemplo acima com um número de teste
3. O ramal `t1-recepcao` deve tocar primeiro (como uma chamada normal
   chegando)
4. Ao atender, deve ouvir o disparo da chamada de saída pro número
   informado

## Teste automatizado
- `queue-api/tests/test_click_to_call.py` — sanitização de número,
  montagem da ação AMI `Originate`, e todas as combinações de
  validação (chave errada, ramal não autorizado, número inválido,
  requisição válida)
- `queue-api/tests/test_server_routes.py` — confirma que a validação
  acontece **antes** de qualquer chamada à AMI (a proteção não é só
  decorativa)
- `tests/test_extensions_conf.py::test_click_to_call_context_dials_via_tdm_gateway`
- `tests/test_docker_compose.py::test_click_to_call_api_key_disabled_by_default`

## Limitações conhecidas (honestidade técnica)
- **A chamada AMI `Originate` de verdade não tem teste de
  integração** — mesma situação já documentada pro tronco TDM, AMI em
  geral e notificações: só valida contra um Asterisk real
- **Uma chave de API única, sem rotação nem por-CRM** — se vários
  sistemas externos vão usar isso, todos compartilham a mesma chave
  hoje; não há como revogar o acesso de um sem trocar pra todos
- **Sem rate limiting** — nada impede um CRM com bug de disparar
  centenas de chamadas por segundo; isso teria custo real numa linha
  de verdade
- **CORS não configurado neste endpoint especificamente** (os outros
  endpoints do queue-api liberam `*`, esse também libera por
  consistência) — se o CRM for uma página web em outro domínio, isso
  já funciona, mas também significa que qualquer página web que
  souber a chave consegue chamar
