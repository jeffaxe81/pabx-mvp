# Manual 37 — Atendente virtual com IA (item #24)

## Leia isto primeiro: o que este item NÃO é
O documento de funcionalidades original descrevia um "atendente
virtual com IA". Isso pode significar coisas bem diferentes em
complexidade — de "um menu que identifica o assunto" até "um robô que
conversa naturalmente por voz, entende respostas, faz perguntas de
volta". **Este projeto implementa a primeira opção**: uma **camada de
triagem única** — o cliente fala uma vez, o sistema classifica a
intenção, e roteia. Não há conversa de ida e volta, não há o
atendente "perguntando mais detalhes" — isso seria um projeto de
escopo bem maior (pipeline de voz em tempo real, gerenciamento de
diálogo com estado, síntese de voz pra resposta), fora do que cabe
aqui.

## O que é feito
1. Cliente liga, é direcionado ao contexto do atendente virtual
2. Ouve um prompt (placeholder de áudio) pedindo pra descrever o
   motivo da ligação
3. O Asterisk grava a fala dele por até 8 segundos (ou até detectar
   silêncio)
4. Um script **AGI** (Asterisk Gateway Interface — a forma padrão do
   Asterisk rodar um script externo no meio da chamada) manda essa
   gravação pro `ai-worker` (manual 36)
5. O `ai-worker` transcreve (Whisper) e classifica a intenção via
   Llama 3: `vendas`, `suporte` ou `outro`
6. O dialplan roteia automaticamente pro destino certo

## Como funciona tecnicamente
```
Cliente fala → Record() (Asterisk) → AGI (atendente_virtual.py)
                                        ↓ POST /api/classify-intent
                                     ai-worker (Whisper + Llama 3)
                                        ↓ {"extension": "1010"}
                                     SET VARIABLE INTENT_DESTINO
                                        ↓
                                     Goto(t1-internal, ${INTENT_DESTINO}, 1)
```

O protocolo AGI (como o script conversa com o Asterisk via stdin/
stdout) está isolado em `agi_protocol.py` — **essa parte tem teste
automatizado completo** (parsing/montagem de comandos, sem precisar
de um Asterisk de verdade rodando). O script principal
(`atendente_virtual.py`) que de fato conversa com o processo Asterisk
e com o `ai-worker` via rede **não é testável neste ambiente** (mesma
limitação do manual 36) — só a função `classify_intent` (a chamada
HTTP) tem teste, usando mocks.

## Segurança de fallback (importante)
Se o `ai-worker` estiver fora do ar, com IA desligada
(`AI_FEATURES_ENABLED=false`), ou qualquer outra falha acontecer, o
script **nunca trava a chamada** — sempre define um destino válido
(fila geral, ramal `1000`). Isso é testado explicitamente
(`test_classify_intent_falls_back_on_network_failure` e afins).

## Como ativar
Depende do `ai-worker` estar configurado e ativo (manual 36,
`AI_FEATURES_ENABLED=true` + Llama 3 baixado). Sem isso, discar a
extensão de teste do atendente virtual ainda funciona, só que sempre
cai na fila geral (comportamento de fallback, não um erro).

## Como testar
1. Configure e ative a IA conforme o manual 36
2. Disque `650` (extensão de teste, tenant 1)
3. Descreva em voz alta o motivo da ligação (ex: "eu queria saber
   sobre os planos disponíveis pra contratar")
4. Confirme que a chamada é roteada pra fila geral (intenção "vendas")
5. Repita descrevendo um problema (ex: "meu serviço parou de
   funcionar") — confirme que roteia pro ramal de suporte

## Teste automatizado
- `asterisk/agi/tests/test_agi_protocol.py` (10 testes) — parsing do
  ambiente AGI, montagem dos comandos `RECORD FILE`/`SET VARIABLE`,
  parsing da resposta do Asterisk
- `asterisk/agi/tests/test_atendente_virtual.py` (3 testes) —
  `classify_intent` com HTTP mockado: sucesso, falha de rede (cai no
  fallback), resposta malformada (cai no fallback)
- `ai-worker/tests/test_intent_classifier.py` (9 testes) — prompt de
  classificação, parsing tolerante da resposta, mapeamento intenção→
  ramal sempre retorna um destino válido
- `tests/test_extensions_conf.py` — contexto existe, roda o AGI,
  tem fallback pra fila geral se `INTENT_DESTINO` não for definido

## Limitações conhecidas (honestidade técnica)
- **Não é conversacional** (ver aviso no topo) — uma interação só,
  sem perguntas de acompanhamento
- **Só 3 categorias de intenção** (vendas/suporte/outro) — pra mais
  granularidade, ajustar `intent_classifier.py`
- **Nunca testado contra um Asterisk/ai-worker reais rodando juntos**
  — a integração completa (AGI real conversando com o processo
  Asterisk) não foi validada neste ambiente
- **Sem confirmação pro cliente** do que foi entendido ("você quer
  falar sobre X, correto?") — a classificação é aplicada direto
- **Grava a fala do cliente** (arquivo `intake-*.wav`) mas não limpa
  esses arquivos automaticamente depois de classificados — ficam
  acumulando em `./recordings/` junto com as outras gravações
