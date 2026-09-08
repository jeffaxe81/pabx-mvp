# Manual 60 — Reprodução de áudio na lista do painel (item #60)

## O que fecha
O manual 53 (lista de áudios existentes) documentou explicitamente
como limitação: **"sem reprodução de áudio na interface — só lista
metadados, não tem um player pra ouvir o arquivo"**. Este item fecha
essa lacuna.

## Um problema real de autenticação, não só de HTML
A solução óbvia (`<audio src="/api/sounds/nome.wav">`) **não
funciona** neste projeto: a tag `<audio>` faz uma requisição HTTP
simples, sem cabeçalhos customizados — e a API exige
`Authorization: Bearer <token>` pra qualquer coisa, inclusive ouvir
um áudio. Sem esse cabeçalho, a API responderia `401` e o áudio nunca
tocaria.

A solução: buscar o arquivo via `fetch()` normal (que já manda o
token, igual o resto do painel faz), pedir o resultado como *blob*,
criar uma URL temporária do navegador (`URL.createObjectURL`), e
apontar um elemento `<audio>` compartilhado pra essa URL.

```
Clique em "Reproduzir" → fetch(/api/sounds/nome.wav, com Authorization)
                            ↓ resposta como blob
                          URL.createObjectURL(blob)
                            ↓
                          <audio>.src = essa URL → .play()
```

## Proteção contra path traversal
O nome do arquivo vem direto da URL, escolhido por quem está
chamando. `is_safe_sound_filename()` valida um padrão restrito
(`[a-z0-9-]{1,60}\.wav`) **antes** de qualquer coisa tocar no sistema
de arquivos — sem isso, alguém poderia tentar pedir
`GET /api/sounds/../../etc/passwd` e potencialmente ler um arquivo
arbitrário do servidor. Isso é testado explicitamente
(`test_serving_sound_file_validates_filename_before_touching_filesystem`).

## Como usar
Painel → seção "Gerar áudio por texto (TTS)" → tabela "Áudios
existentes" → botão "Reproduzir" em qualquer linha.

## Como testar manualmente
1. `docker compose up -d`
2. Gere um áudio pela seção de TTS (ou use um dos placeholders já
   existentes)
3. Clique "Reproduzir" na tabela — confirme que o áudio toca
4. Tente acessar `GET /api/sounds/../../../etc/passwd` diretamente
   (sem passar pelo botão) — confirme que é recusado com erro `400`

## Teste automatizado
- `admin-api/tests/test_sounds.py` (6 testes novos) —
  `is_safe_sound_filename`: aceita nome válido, recusa tentativas de
  path traversal (`../`, encoding de URL), recusa separador de
  caminho, recusa extensão diferente de `.wav`, recusa maiúsculas/
  caracteres especiais, recusa vazio/`None`
- `admin-api/tests/test_server_security.py` (2 testes novos) —
  validação de nome ANTES de ler o arquivo, exige autenticação
- `tests/test_admin_html.py` (3 testes novos) — botão presente por
  linha, busca via `fetch()` com `Authorization` (não `<audio src>`
  direto), cria URL de objeto e toca
- **890 testes no total**, em 8 suítes

## Limitações conhecidas (honestidade técnica)
- **Um único player compartilhado** — tocar um áudio novo interrompe
  o anterior (não é uma limitação real na prática, já que ouvir dois
  áudios ao mesmo tempo não faria sentido aqui, mas vale registrar)
- **Sem controle de volume/progresso visível na interface** — o
  elemento `<audio>` fica oculto (`display:none`), então não há
  barra de progresso nem botão de pausa visíveis; só toca do início
  ao fim
- **URLs de objeto (`createObjectURL`) não são revogadas** — cada
  clique em "Reproduzir" cria uma nova URL temporária sem chamar
  `URL.revokeObjectURL()` na anterior; em uma sessão muito longa com
  muitos áudios diferentes tocados, isso acumula memória não liberada
  no navegador (impacto pequeno na prática, mas real)
- **Nunca testado contra um Asterisk real** — mesma situação de
  sempre; aqui, especificamente, nunca confirmado que os áudios
  gerados por TTS (manual 48) realmente têm o formato que o
  `<audio>` do navegador consegue tocar sem problema (ex: taxa de
  amostragem compatível)
