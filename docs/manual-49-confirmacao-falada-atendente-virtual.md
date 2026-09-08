# Manual 49 — Confirmação falada do atendente virtual (fase 2 do TTS)

## O que é
Fase 2 do backlog #48 — o atendente virtual com IA (manual 37) agora
**confirma em voz** o que entendeu, antes de transferir a chamada.
Antes disso, a classificação de intenção acontecia em silêncio: o
cliente falava, e a chamada simplesmente era roteada, sem nenhum
retorno perceptível do que o sistema entendeu.

## Como funciona
```
Cliente descreve o motivo → Whisper transcreve → Llama 3 classifica
                                                      ↓
                                          Piper sintetiza a confirmação
                                                      ↓
                              Toca "Entendi que você quer falar sobre
                               vendas. Vou te transferir." pro cliente
                                                      ↓
                                    Roteia pro ramal certo (manual 37)
```

Frases curtas e fixas por intenção (não geradas dinamicamente por
LLM) — mantém previsível e rápido, sem risco do modelo de linguagem
"inventar" algo estranho na confirmação:
- **Vendas**: "Entendi que você quer falar sobre vendas. Vou te
  transferir."
- **Suporte**: "Entendi que você precisa de suporte. Vou te
  transferir."
- **Outro/incerto**: "Não tenho certeza do assunto, vou te transferir
  pra um atendente."

## Best-effort, nunca bloqueia o roteamento
Se a síntese de voz falhar por qualquer motivo (motor indisponível,
erro de rede, etc.), `confirmation_filename` vem `None` na resposta
do `ai-worker`, e o script AGI simplesmente **pula** o `STREAM FILE`
— a chamada continua sendo roteada normalmente, só sem o toque a
mais da confirmação falada. A confirmação é um recurso "a mais",
nunca pode virar um ponto de falha do fluxo principal.

## Ordem importa
O áudio de confirmação **precisa tocar antes** da variável
`INTENT_DESTINO` ser definida — senão a confirmação chegaria tarde
demais, depois que o dialplan já tivesse decidido o roteamento. Isso
é testado explicitamente
(`test_main_streams_confirmation_before_setting_destination`).

## O que foi alterado
- `ai-worker/intent_classifier.py`: `build_confirmation_phrase(intent)`
  — frases fixas por intenção, sempre retorna algo (nunca vazio)
- `ai-worker/server.py`: `_handle_classify_intent` agora também chama
  `_synthesize_confirmation()` (Piper, best-effort) e inclui
  `confirmation_filename` na resposta JSON
- `asterisk/agi/agi_protocol.py`: `build_stream_file_command()` — o
  comando AGI `STREAM FILE`, usado pra tocar áudio durante a chamada
- `asterisk/agi/atendente_virtual.py`: `classify_intent()` agora
  retorna um dict (antes retornava só a extensão como string); `main()`
  toca o `STREAM FILE` antes do `SET VARIABLE`

## Como testar manualmente
1. `docker compose up -d`, com `AI_FEATURES_ENABLED=true`
2. Disque `650` (teste do atendente virtual, tenant 1)
3. Descreva um motivo de vendas em voz alta
4. Confirme que ouve "Entendi que você quer falar sobre vendas. Vou
   te transferir." antes de ser conectado à fila

## Teste automatizado
- `ai-worker/tests/test_intent_classifier.py` (3 testes novos) —
  frase certa por intenção, nunca vazia, fallback pra "outro"
- `ai-worker/tests/test_server_security.py` — confirmação incluída
  na resposta nos dois caminhos (com e sem transcrição), síntese
  nunca propaga exceção
- `asterisk/agi/tests/test_agi_protocol.py` (2 testes novos) —
  `STREAM FILE` montado corretamente, com e sem dígitos de escape
- `asterisk/agi/tests/test_atendente_virtual.py` (4 testes
  atualizados/novos) — resposta com/sem áudio de confirmação, **ordem
  correta** (confirmação antes do destino), comportamento sem
  confirmação disponível
- **768 testes no total**, em 7 suítes

## Limitações conhecidas (honestidade técnica)
- **Frases fixas, não geradas dinamicamente** — não repete de volta o
  que o cliente disse (ex: "entendi que você quer X"), só confirma a
  categoria classificada; um assistente mais sofisticado poderia
  parafrasear o pedido original
- **Só a intenção é confirmada, não o ramal de destino** — o cliente
  não ouve "vou te transferir pro ramal 1010", só a categoria
- **Arquivos de confirmação se acumulam** sem limpeza automática em
  `asterisk/sounds/custom/` (nomes aleatórios `tts-*.wav`) — mesma
  limitação já registrada no manual 48 pra geração de áudio em geral
- **Nunca testado contra Piper/Asterisk de verdade rodando juntos** —
  mesma situação já documentada pro resto das integrações de IA e AGI
  deste projeto
