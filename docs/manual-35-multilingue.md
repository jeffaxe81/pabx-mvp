# Manual 35 — Atendimento multilíngue (item #30)

## O que é
Logo no início da URA, o cliente escolhe o idioma (português, inglês
ou espanhol) — e a partir daí, tanto o **menu** quanto a **fila de
atendimento** passam a ser específicos daquele idioma. Isso é o
último item do backlog que dá pra construir só com configuração de
dialplan, sem depender de IA (diferente de transcrição/tradução
automática).

## Como funciona
1. Cliente liga, é identificado como não-VIP (VIP pula direto pro
   ramal dele, sem passar por idioma nenhum)
2. Ouve o menu de seleção de idioma (placeholder de áudio) e digita
   `1` (português, padrão), `2` (inglês) ou `3` (espanhol)
3. Isso define duas variáveis de canal que valem pro resto da
   chamada: `${FILA_IDIOMA}` (qual fila usar) e `${MENU_PRINCIPAL}`
   (qual áudio de menu tocar)
4. Segue o fluxo normal (feriado/horário comercial), só que usando
   essas variáveis em vez de valores fixos

## As filas por idioma
Cada idioma tem sua própria fila (`fila-t1`, `fila-t1-en`,
`fila-t1-es`), com um conjunto de membros que "falam" aquele idioma —
não é só uma questão de tocar áudio diferente, a chamada realmente
**vai pra um atendente diferente** dependendo do idioma escolhido.

Neste MVP, com só 2 telefonistas de exemplo:
- `t1-recepcao` cobre português (fila padrão) **e** inglês
- `t1-recepcao-2` cobre espanhol

Pra adicionar um atendente que fala outro idioma (ou mais idiomas),
adicione ele como `member` na(s) fila(s) correspondente(s) em
`asterisk/queues.conf`.

## Onde isso NÃO se aplica (limitação de escopo deliberada)
Fora de horário, feriado, pesquisa de satisfação, callback e as
mensagens de voz continuam **só em português** neste MVP — só o
fluxo principal (seleção de idioma → menu → fila) é multilíngue de
verdade. Estender os outros fluxos seguiria o mesmo padrão (variável
de idioma + áudio por idioma), mas não foi feito agora pra manter o
escopo gerenciável.

## Como testar manualmente
1. `docker compose up -d`
2. Disque `700` (extensão de teste da URA)
3. No menu de idioma, aperte `2` (inglês)
4. Confirme que ouve o placeholder de áudio **diferente** do padrão
   (2 beeps em vez de 1)
5. Aperte `1` no menu seguinte (vendas/fila)
6. Confirme que a chamada toca **só em `t1-recepcao`**, não em
   `t1-recepcao-2` (já que ela não está na fila de inglês)
7. Repita escolhendo espanhol (`3`) — confirme que agora só
   `t1-recepcao-2` toca

## Teste automatizado
- `tests/test_ami_config.py::test_language_specific_queues_exist` —
  as duas filas novas existem com os membros certos
- `tests/test_extensions_conf.py`:
  - `test_vip_check_has_priority_over_language_selection`
  - `test_language_selection_offers_three_languages`
  - `test_language_selection_sets_language_specific_menu_audio`
  - `test_business_hours_menu_uses_selected_language_audio`
  - `test_direct_dial_to_1000_defaults_to_portuguese_queue` — garante
    que discar `1000` direto (sem passar pela URA) continua caindo em
    português, não quebra o comportamento já existente
- `tests/test_ura_sounds.py` — os 4 placeholders de áudio novos
  existem e são WAV válidos

## Limitações conhecidas (honestidade técnica)
- **Áudio placeholder** (beeps com frequências diferentes por
  idioma), mesma situação de todos os outros pontos da URA — precisa
  trocar por gravações reais em cada idioma antes de produção
- **Só o fluxo principal é multilíngue** (ver seção acima) — fora de
  horário, feriado, satisfação, callback e voicemail continuam em
  português
- **Sem detecção automática de idioma** (por número/país, por
  histórico do cliente) — é sempre pergunta explícita por dígito
- **"Atendente fala idioma X" é só participação numa fila** — não há
  um cadastro formal de "idiomas que cada atendente fala" no painel
  de administração; é editar `queues.conf` na mão
- **Sem tradução em tempo real** — cada idioma tem seu próprio
  atendente dedicado; não há tradução automática de uma conversa
  entre pessoas que falam idiomas diferentes (isso entraria na
  categoria dos itens de IA, backlog #21-24)
