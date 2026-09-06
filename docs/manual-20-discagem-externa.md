# Manual 20 — Regras de discagem externa (item #14)

## O que é
Três coisas que faltavam na discagem de saída:
1. **Bloqueio de números** — impedir que certos números sejam
   discados (números caros, suspeitos, ou qualquer regra da empresa)
2. **Rota por prefixo** — números com prefixo diferente saem por um
   tronco diferente (ex: uma operadora mais barata pra internacional)
3. **Múltiplos troncos** — o projeto tinha só `gateway-tdm`; agora
   tem também `gateway-tdm-2` (operadora alternativa/backup)

## Como funciona
Quando um ramal disca `0` + número, o dialplan agora faz duas
checagens antes de discar de verdade:

```
exten => _0.,1,Set(DESTINO=${EXTEN:1})
 same => n,GotoIf(bloqueado?)      ; 1) está na lista de bloqueio?
 same => n,GotoIf(prefixo "0"?)    ; 2) tem um 0 extra (discou "00")?
 same => n,Dial(...@gateway-tdm)   ; rota padrão
```

- **Bloqueio**: consulta o **AstDB** (banco de dados interno do
  Asterisk, embutido, sem precisar de outro serviço) na família
  `blocklist` — `${DB(blocklist/${DESTINO})}`. Se o número estiver lá,
  a chamada cai em `Congestion()` (tom de ocupado) em vez de discar
- **Rota alternativa**: discar `00` + número (um zero a mais) manda a
  chamada pelo `gateway-tdm-2` em vez do padrão — é o mecanismo de
  "prefixo escolhe a rota", generalizável pra outros prefixos/operadoras

## Como gerenciar a lista de bloqueio
Pelo painel de administração (manual 16), nova seção "Números
bloqueados": digite o número, clique "Bloquear". Por trás, isso vira
uma ação AMI `DBPut` na família `blocklist` — não precisa de reload
nem de reiniciar nada, o dialplan já consulta o AstDB em tempo real a
cada chamada.

Ou direto pela API (autenticada, mesmo token do painel):
```bash
curl -X POST http://<ip>:8091/api/blocklist \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"number": "0900123456"}'
```

## Como configurar o tronco alternativo
Em `asterisk/pjsip.conf`, seção `[gateway-tdm-2]` — mesmo padrão do
`gateway-tdm` original (manual 04), troque o IP de exemplo
(`192.168.1.201`) pelo IP real do seu segundo gateway/operadora.

## Como testar manualmente
1. `docker compose up -d`
2. Pelo painel de administração, bloqueie um número de teste (ex:
   `08000000000`)
3. De um ramal, disque `0` + esse número — deve dar tom de
   ocupado/congestionamento em vez de tentar discar
4. Desbloqueie o número — confirme que agora disca normalmente
5. Disque `00` + qualquer número — confirme (via log do Asterisk,
   `pjsip set logger on` ou CLI) que a tentativa de chamada foi pro
   `gateway-tdm-2`, não pro `gateway-tdm`

## Teste automatizado
- `admin-api/tests/test_blocklist.py` — validação/sanitização de
  número (mesma lógica já usada no click-to-call)
- `admin-api/tests/test_server_security.py` — rotas de bloqueio
  também checam autenticação antes de mexer no AMI
- `tests/test_pjsip_conf.py` — `gateway-tdm-2` existe e segue o mesmo
  padrão do tronco original
- `tests/test_extensions_conf.py` — checagem de bloqueio acontece
  antes do `Dial()`, número bloqueado cai em `Congestion()` (não em
  outro `Dial`), rota alternativa usa o segundo tronco de verdade

## Limitações conhecidas (honestidade técnica)
- **Só tenant 1** — o tenant 2 continua discando direto, sem checagem
  de bloqueio nem rota alternativa (mesma limitação de escopo já
  aceita no painel de administração, manual 16)
- **Sem lista de números permitidos** (allowlist) — só bloqueio
  explícito, não existe "só esses números podem ligar pra fora"
- **Sem limite de gastos por ramal** — isso é o item #32 (detecção de
  fraude) do backlog, ainda não implementado
- **`DBGetTree`/`DBPut`/`DBDel` via AMI não têm teste de integração
  real** — mesma situação já documentada pro resto das integrações
  AMI deste projeto: só valida contra um Asterisk de verdade
- **Um único prefixo de rota alternativa** (`00`) — pra múltiplas
  regras de prefixo (ex: internacional vs. celular vs. fixo em rotas
  diferentes), o dialplan precisaria de mais branches, seguindo o
  mesmo padrão
