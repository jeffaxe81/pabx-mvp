# Manual 48 — Síntese de voz / TTS (item #48)

## Leia isto primeiro — a decisão de licenciamento
O usuário pediu avaliação de TTS via **Coqui TTS / XTTS**. A
investigação encontrou um problema real:

- **XTTS-v2** (o modelo multilíngue com vozes neurais e clonagem de
  voz da Coqui) é distribuído sob a **Coqui Public Model License
  (CPML)**, que **proíbe uso comercial sem uma licença paga da
  Coqui**
- A empresa **Coqui.ai encerrou operações em 2024** — hoje não há
  caminho claro pra obter essa licença comercial, mesmo que alguém
  queira pagar por ela
- Esse é um assunto que muda com o tempo — confirme o estado atual
  antes de decidir, não confie só neste manual

Por isso, a arquitetura tem **dois motores desacoplados**, não um só:

| | **Piper** (padrão) | **XTTS-v2** (opcional) |
|---|---|---|
| Licença | MIT | Coqui Public Model License — **não-comercial apenas** |
| Ativado por padrão | Sim (junto com `AI_FEATURES_ENABLED`) | **Não** — precisa de `TTS_XTTS_ENABLED=true` explícito |
| Qualidade | Neural, boa, sem clonagem de voz | Neural, mais sofisticada, com clonagem de voz |
| Uso comercial | Seguro | **Não** — só ative se seu uso for genuinamente não-comercial |

## O que foi implementado nesta fase
**Prioridade URA**, como decidido — o admin digita o texto de um
anúncio (ex: a saudação principal) e o sistema gera o `.wav` na hora,
sem precisar de locutor nem estúdio.

**Ainda não implementado**: resposta falada do atendente virtual com
IA (manual 37) — a integração de TTS ali ficou como próximo passo,
não fazia parte desta fase.

## Arquitetura
```
Painel (admin) → admin-api (proxy, admin-only)
                    ↓ POST /api/sounds/generate
                  ai-worker → POST /api/tts
                    ↓ valida (texto, idioma, motor, nome de arquivo)
                    ↓ Piper (padrão) ou XTTS (se TTS_XTTS_ENABLED)
                  grava .wav DIRETO em asterisk/sounds/custom/
                    ↓
                  Playback(custom/nome) no dialplan já encontra o arquivo
```

Sem proxy de bytes de áudio entre serviços — o `ai-worker` escreve
**direto** na pasta que o Asterisk lê (volume Docker compartilhado),
mesmo padrão de simplicidade já usado no resto do projeto.

## Duas flags separadas, de propósito
`AI_FEATURES_ENABLED` (geral) e `TTS_XTTS_ENABLED` (específica) são
independentes — ligar a IA em geral **nunca** libera XTTS sozinho.
Isso é testado explicitamente
(`test_xtts_has_its_own_separate_flag_from_ai_features`).

## Como usar
1. Ligue `AI_FEATURES_ENABLED=true` no `ai-worker` (manual 36)
2. No painel, seção "Gerar áudio por texto (TTS)"
3. Digite o nome do arquivo (ex: `menu-principal-pt` — sobrescreve o
   placeholder existente) ou deixe vazio pra um nome aleatório
4. Escolha idioma e motor (Piper por padrão)
5. Digite o texto, clique "Gerar áudio"
6. O áudio já está disponível pro dialplan (`custom/menu-principal-pt`)
   assim que a geração termina — sem precisar de reload

Escolher XTTS-v2 na interface exige uma **confirmação extra**
(popup), lembrando da licença não-comercial antes de prosseguir.

## Como testar manualmente
1. `docker compose up -d`
2. Gere um áudio com o nome `menu-principal-pt` e um texto de teste
3. Confirme que o arquivo apareceu em
   `asterisk/sounds/custom/menu-principal-pt.wav`
4. Ligue pro `700` (teste de URA) — confirme que ouve o áudio novo
   em vez do placeholder antigo

## Teste automatizado
- `ai-worker/tests/test_tts_service.py` (13 testes) — validação
  completa: texto obrigatório, limite de tamanho, idiomas suportados,
  motor válido, **XTTS recusado quando desligado** (não redirecionado
  silenciosamente pro Piper), nome de arquivo opcional com validação
  de formato
- `ai-worker/tests/test_server_security.py` — flag checada antes de
  sintetizar, validação antes de chamar qualquer motor, XTTS com flag
  própria separada, dispatch pro motor certo
- `admin-api/tests/test_server_security.py::test_generate_sound_requires_admin_role`
- `tests/test_docker_compose.py` — volume compartilhado entre
  `ai-worker` e Asterisk, flag do XTTS desligada por padrão,
  `admin-api` sabe onde encontrar o `ai-worker`
- `tests/test_admin_html.py` — seção escondida de supervisor, aviso
  de licenciamento presente no texto, escolher XTTS exige confirmação
  extra
- **758 testes no total**, em 7 suítes

## Limitações conhecidas (honestidade técnica)
- **Nunca testado contra `piper-tts`/`coqui-tts` de verdade** — mesma
  situação já documentada pro resto das integrações de IA deste
  projeto; a assinatura exata da API pode variar por versão
- **Resposta falada do atendente virtual (manual 37) não foi
  integrada** — ficou fora do escopo desta fase, é o próximo passo
  natural
- **XTTS-v2 vem comentado no `requirements.txt`** de propósito — é
  uma dependência pesada (PyTorch + modelos grandes); ativar exige
  descomentar a linha e reconstruir a imagem, não só mudar a variável
  de ambiente
- **Sem lista de áudios gerados na interface** — o painel gera, mas
  não mostra um histórico do que já foi criado nem permite
  reproduzir/conferir antes de considerar pronto
- **Nome de arquivo permite sobrescrever qualquer áudio existente**
  sem aviso — gerar com o nome `aviso-gravacao` (manual 40), por
  exemplo, substitui o áudio de conformidade legal sem confirmação
  extra específica pra esse caso
