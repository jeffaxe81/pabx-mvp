# Manual 07 — Transferência assistida (com consulta)

## O que é
Permite à telefonista falar com o colega antes de completar a
transferência, em vez de transferir às cegas. Complementa a
transferência cega que já existia (clique num colega no painel de
presença, ou o campo de texto + botão "Transferir").

## Como funciona (fluxo)
1. Telefonista está em chamada ativa com o cliente (chamada A)
2. Digita o ramal do colega e clica **"Consultar antes de transferir"**
3. A chamada A é colocada em espera (`hold()`), e uma nova chamada
   (B) é feita para o colega
4. Telefonista fala com o colega na chamada B
5. Se o colega aceita: clica **"Completar transferência"** — a
   chamada A recebe um REFER para o ramal do colega, e a telefonista
   sai das duas chamadas
6. Se o colega recusa ou não quer: clica **"Cancelar"** — a chamada B
   é encerrada e a chamada A volta automaticamente da espera

## Honestidade técnica importante
Isso **não** é um "attended transfer" com `Replaces` (RFC 3891), que
faria o cliente ser conectado diretamente à *mesma* ligação que a
telefonista teve com o colega, de forma completamente transparente. O
JsSIP não expõe de forma pública e estável os identificadores internos
de diálogo SIP (Call-ID / tags) necessários para montar esse
`Replaces` de forma confiável.

Na prática, o que acontece: ao completar, o **cliente recebe um novo
convite de chamada para o ramal do colega** (REFER simples) — ou seja,
o cliente ouve um pequeno silêncio/re-toque no momento da troca, em
vez de uma transição 100% imperceptível. A telefonista já validou com
o colega que ele quer/pode atender, então na prática funciona bem
como transferência assistida — só não é "invisível" no áudio do
cliente.

## Como testar manualmente
1. Três softphones/ramais: cliente (A), telefonista web (recepção),
   colega (B)
2. Cliente liga pra recepção (ramal 1000)
3. Telefonista atende, digita o ramal de B, clica "Consultar antes de
   transferir"
4. Confirme: A fica em espera (silêncio/música de espera do lado do
   cliente), telefonista ouve tocando em B
5. B atende — botão "Completar transferência" deve ficar habilitado
6. Clique em completar — confirme que A e B ficam conectados
   diretamente, e a telefonista sai da chamada
7. Repita o fluxo, mas clique "Cancelar" em vez de completar — confirme
   que a chamada com A volta automaticamente da espera

## Teste automatizado
`tests/test_webphone_html.py::test_assisted_transfer_uses_hold_before_consulting`
`tests/test_webphone_html.py::test_assisted_transfer_completion_sends_refer_and_cleans_up_both_legs`
`tests/test_webphone_html.py::test_consult_call_does_not_get_rejected_as_second_call`

## Limitações conhecidas
- Não é um bridge invisível (ver seção acima) — o cliente percebe a
  troca
- Se o colega não atender, não há timeout automático — a telefonista
  precisa cancelar manualmente
- Não há como voltar e forth entre A e B mais de uma vez (sem "alternar
  chamadas" tipo hold/swap múltiplo) — é consulta única seguida de
  completar ou cancelar
