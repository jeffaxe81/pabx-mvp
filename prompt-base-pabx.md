# Projeto: PABX Open Source (SIP)

## Contexto
Estou desenvolvendo um PABX baseado em Asterisk (PJSIP), 100% SIP,
começando por um MVP simples e evoluindo aos poucos. Repositório:
https://github.com/jeffaxe81/pabx-mvp

## Estado atual

**Core**
- Asterisk rodando via Docker Compose
- Ramais SIP multi-tenant (contextos isolados `t1-internal`, `t2-internal`)
- Dialplan básico: chamadas internas, teste de eco (600), correio de
  voz (*97)

**Segurança**
- Sinalização SIP via TLS (porta 5061) e mídia via SRTP
  (`media_encryption=sdes`), com certificado self-signed em
  `asterisk/certs/` (trocar por certificado válido em produção)

**Multi-tenant**
- Contextos isolados por tenant (t1, t2), numeração pode repetir entre
  tenants sem conflito; voicemail também separado por tenant

**Tronco TDM**
- Endpoint `gateway-tdm` no PJSIP, pensado para um gateway físico
  (Grandstream GXW, AudioCodes MP-11x, Patton) fazer a ponte TDM↔SIP;
  roteamento de DID por tenant em `[from-tdm-gateway]`

**Auto-provisionamento**
- Servidor HTTP (nginx) servindo arquivos de config por MAC address,
  gerados via `provisioning/generate.py` a partir de `devices.json` e
  templates por fabricante (hoje só Yealink)

**Fila de atendimento**
- Fila `fila-t1` com a telefonista como membro; chamadas sem DID
  esperam com pickup dirigido (a telefonista escolhe qual atender,
  não só a mais antiga)
- Serviço `queue-api` (Python, stdlib only) fala AMI com o Asterisk,
  expõe a fila via HTTP; webphone faz polling a cada 3s
- Sem teste de integração real (precisa de Asterisk rodando) - só a
  lógica de parsing/estado é testada automaticamente

**Notificação de chamada perdida**
- Detecção via AMI (DialEnd sem ANSWER, QueueCallerAbandon)
- Email (SMTP) e/ou WhatsApp (Meta Cloud API), desligado por
  padrão até configurar credenciais reais em docker-compose.yml
- Histórico visível no webphone (painel "Chamadas perdidas")
  independente de notificação estar ligada

**Discagem por clique a partir do CRM (click-to-call)**
- API HTTP protegida por chave (CLICK_TO_CALL_API_KEY, vazia por
  padrão = desligado) + allowlist de ramais
- Originate via AMI: liga pro ramal da telefonista, ela atende,
  Asterisk completa pro número do cliente

**Painel de administração web**
- CRUD de ramais do tenant 1 (admin/ + admin-api/), login com hash
  PBKDF2, sessão por token; desligado por padrão sem ADMIN_PASSWORD_HASH
- Gera pjsip_dynamic.conf/extensions_dynamic_*.conf/voicemail_dynamic_t1.conf
  via #include, recarrega Asterisk via AMI sem reiniciar
- Só tenant 1, sem 2FA, sem perfis de permissão (ver itens #19/#20
  do backlog fase 2/3) - ver limitações no docs/manual-16

**PWA instalável com notificação nativa**
- manifest.json + ícones + service worker (webphone/); instalável
  como app
- Campainha via Web Audio (sem arquivo externo) + notificação
  nativa do SO em toda chamada recebida, mesmo com aba em 2º plano
- NÃO é Push real (não funciona com navegador fechado) - exigiria
  servidor de push + VAPID, fora do escopo

**Múltiplas telefonistas simultâneas**
- 2 operadoras (t1-recepcao, t1-recepcao-2), ramal 1000 agora entra
  na fila (Queue) em vez de discar fixo; fila usa strategy=rrmemory
- Pickup dirigido agora exige extension no corpo da requisição -
  cada operadora só recebe o que ela mesma puxou
- Ramais diretos 1010/1011 pra uso interno (falar com uma
  operadora específica, não com "a recepção")

**Dashboard de métricas do dia**
- Painel no webphone: chamadas totais, atendidas, perdidas, TMA,
  taxa de perdidas - via CDR do Asterisk (cdr.conf + cdr_manager.conf)
- Em memória, zera à meia-noite, sem separação por tenant ainda

**Multi-chamada**
- Até 2 linhas simultâneas; atender a linha 2 põe a linha 1 em
  espera automaticamente; barra de troca de linha; volta sozinho
  pra outra linha se a ativa cair
- 3ª chamada simultânea continua sendo recusada (limite do MVP)

**Gravação de chamadas**
- Automática via monitor-type=mixmonitor na fila, e MixMonitor()
  explícito nos pontos fora da fila (ramal 1000 direto, pickup)
- Player embutido no webphone (painel "Gravações"), servido pelo
  queue-api (GET /api/recordings, GET /recordings/<nome>)
- Sem retenção/expurgo automático, sem autenticação no endpoint -
  ver limitações no docs/manual-09

**Telefonista web (WebRTC)**
- Interface em `webphone/index.html` (JsSIP): discador, atender,
  recusar, mudo, espera, transferência cega, histórico de chamadas da
  sessão
- Presença/BLF em tempo real dos colegas (SIP SUBSCRIBE aos hints do
  Asterisk): bolinha livre/tocando/em chamada
- Clicar num colega liga direto pra ele (se ocioso) ou transfere a
  chamada atual na hora (se em chamada)
- Transferência assistida: consulta o colega antes de completar a
  transferência (hold + chamada de consulta + REFER); não é bridge
  invisível - o cliente percebe a troca (ver docs/manual-07)
- Requer WSS habilitado (`asterisk/http.conf`, porta 8089) e endpoint
  com `webrtc=yes` (`t1-recepcao`, ramal 1000)

## Stack
- Asterisk + PJSIP
- Docker / Docker Compose
- JsSIP (webphone WebRTC)
- Softphones para teste: Zoiper / Linphone

## Ideias futuras (backlog, ainda não implementadas)
1. ~~Transferência assistida~~ — IMPLEMENTADO, ver docs/manual-07
2. ~~Fila de atendimento~~ — IMPLEMENTADO (pickup dirigido via AMI), ver docs/manual-08
3. ~~Gravação de chamadas~~ — IMPLEMENTADO (MixMonitor + monitor da fila), ver docs/manual-09
4. ~~Multi-chamada~~ — IMPLEMENTADO (2 linhas, hold automático ao atender/trocar), ver docs/manual-10
5. ~~Notificação de chamada perdida~~ — IMPLEMENTADO (email/WhatsApp via AMI DialEnd/QueueCallerAbandon), ver docs/manual-11
6. ~~Discagem por clique a partir do CRM~~ — IMPLEMENTADO (API com chave, Originate via AMI), ver docs/manual-12
7. ~~Dashboard de métricas do dia~~ — IMPLEMENTADO (via CDR do Asterisk; ainda sem separação por tenant), ver docs/manual-13
8. ~~Múltiplas telefonistas simultâneas~~ — IMPLEMENTADO (2 operadoras, fila rrmemory, pickup por-operador), ver docs/manual-14
9. ~~PWA instalável com notificação nativa~~ — IMPLEMENTADO (manifest, service worker, campainha via Web Audio; sem Push real), ver docs/manual-15
10. ~~Painel de administração web~~ — IMPLEMENTADO (CRUD de ramais do
    tenant 1 via admin-api + #include no Asterisk, reload via AMI),
    ver docs/manual-16

## Backlog original (10/10 IMPLEMENTADO) ✅

Todos os 10 itens do backlog original foram concluídos - ver
`docs/README.md` pro índice completo dos 16 manuais.

## Itens 12-16 (completar o que existia parcial) - TODOS IMPLEMENTADOS ✅

## Backlog fase 2/3 (a partir do documento de funcionalidades completo)

Comparado contra um documento de funcionalidades de PABX/CCaaS
completo (roadmap enviado em 2026-09-06). Itens que **já existem** no
produto (ramais SIP, filas, correio de voz, gravação, softphone web,
click-to-call, multi-telefonista, transferência, multi-chamada, BLF,
PWA) não estão listados aqui de novo — só o que falta ou está parcial.

**Completar o que já existe (parcial)**
11. ~~Painel operacional em tempo real consolidado~~ — IMPLEMENTADO
    (fila + estado de ramais via AMI ExtensionStatus + métricas numa
    tela só), ver docs/manual-17
12. ~~Relatórios por atendente/tenant/período~~ — IMPLEMENTADO
    (call_log.jsonl persistente, extraído do CDR, agrupável por
    operador/tenant/dia), ver docs/manual-18
13. ~~Integração CRM PABX→CRM (screen-pop)~~ — IMPLEMENTADO (link
    clicável configurável + webhook opcional via DialBegin), ver
    docs/manual-19
14. ~~Regras de discagem externa~~ — IMPLEMENTADO (bloqueio via
    AstDB gerenciado pelo painel, rota alternativa por prefixo,
    2º tronco gateway-tdm-2), ver docs/manual-20
15. ~~Busca de gravações e retenção~~ — IMPLEMENTADO (filtro por
    número/destino/período extraído do nome do arquivo, expurgo
    automático opt-in), ver docs/manual-21
16. ~~E-mail de correio de voz~~ — IMPLEMENTADO (script mail_relay.py
    repassa pro SMTP, desligado por padrão), ver docs/manual-22

**Fase 2 — Gestão (novo)**
17. ~~URA (menus de voz)~~ — IMPLEMENTADO (modo feriado via AstDB
    com prioridade sobre horário comercial, roteamento por dígito,
    áudio placeholder), ver docs/manual-23
18. ~~Grupos de toque~~ — IMPLEMENTADO (ramal 900 simultâneo, 901
    em sequência, com hints combinados), ver docs/manual-24
19. ~~Permissões e perfis~~ — IMPLEMENTADO (admin/supervisor no
    painel de administração, backend checa papel antes de mutar),
    ver docs/manual-25
20. ~~Autenticação em dois fatores (2FA)~~ — IMPLEMENTADO (TOTP
    RFC 6238 puro stdlib, validado contra vetor de teste oficial,
    autoatendimento por usuário), ver docs/manual-26

**Fase 2 completa (17-20) ✅**

**Fase 3 — Diferenciais e IA (novo)**
21. ~~Transcrição automática de chamadas~~ — IMPLEMENTADO (Whisper
    local via faster-whisper, servico ai-worker), ver docs/manual-36
22. ~~Resumo automático de chamada~~ — IMPLEMENTADO (Llama 3 local
    via Ollama), ver docs/manual-36 com identificação de tarefas
23. ~~Análise de sentimento~~ — IMPLEMENTADO (Llama 3 local via
    Ollama), ver docs/manual-36 (detectar insatisfação/urgência)
24. ~~Atendente virtual com IA~~ — IMPLEMENTADO como camada de
    triagem única (nao conversacional) via AGI + ai-worker, ver
    docs/manual-37

**BACKLOG COMPLETO - todos os itens 1-34 (Fase 1, Fase 2, Fase 3 e
Infraestrutura) foram implementados.** Provedor de IA escolhido:
local (Whisper + Llama 3 via Ollama), sem nuvem, sem custo por
requisicao - ver docs/manual-36 e docs/manual-37 para avisos de
honestidade tecnica sobre o que nao pode ser testado neste ambiente. (primeira camada de triagem)
25. ~~Discador automático (campanhas)~~ — IMPLEMENTADO (reaproveita
    contexto do click-to-call, retry ate 3 tentativas), ver
    docs/manual-30
26. ~~Chamada de retorno (callback)~~ — IMPLEMENTADO (opção 9 na
    URA, fila FIFO, Originate direto pro cliente), ver docs/manual-31
27. ~~Pesquisa de satisfação pós-atendimento~~ — IMPLEMENTADO (opção
    c/g do Asterisk mantém cliente na linha, nota 1-5 associada ao
    atendente via DIALEDPEERNAME), ver docs/manual-32
28. ~~Transferência inteligente por regra~~ — IMPLEMENTADO (cliente
    VIP via AstDB com prioridade máxima, retorno automático real via
    DIALSTATUS/QUEUESTATUS), ver docs/manual-33
29. ~~Presença corporativa avançada~~ — IMPLEMENTADO (4 estados
    manuais, autoatendimento, mesclado com BLF automático); SEM
    sincronização de calendário (categoria dos itens de IA), ver
    docs/manual-34
30. ~~Atendimento multilíngue~~ — IMPLEMENTADO (seleção pt/en/es na
    URA, fila+áudio próprios por idioma; só o fluxo principal, ver
    limitação), ver docs/manual-35

**Fase 3 sem IA completa (25-30, exceto os que dependem de provedor externo) ✅**

**Infraestrutura e segurança (novo)**
31. ~~Lista de bloqueio~~ — IMPLEMENTADO junto com o item #14
    (bloqueio de números via AstDB, gerenciável pelo painel), ver
    docs/manual-20
32. ~~Detecção de fraude~~ — IMPLEMENTADO (volume anormal via
    DialBegin, bloqueio automático reaproveitando AstDB do manual
    20, limite de gasto), ver docs/manual-27
33. ~~Backup automático~~ — IMPLEMENTADO (empacota config+dados
    diariamente, restauração documentada); NÃO é alta disponibilidade
    de verdade (sem failover) - ver docs/manual-28 pro aviso honesto
34. ~~Monitoramento de qualidade de chamada~~ — IMPLEMENTADO (RTCP
    via hangup handler + UserEvent), ver docs/manual-29

**Itens de infraestrutura completos (31-34) ✅**

**Fora de escopo deste projeto (mencionados no documento, mas são
produtos à parte, não itens de backlog)**
- Videoconferência
- Aplicativo móvel nativo (a PWA do manual 15 cobre parte disso em
  Android/Chrome, mas não é o mesmo que um app nativo)
- Integração ampla com WhatsApp como inbox omnichannel (hoje só
  enviamos notificação de chamada perdida, manual 11)
- Agenda/contatos compartilhados e integração com calendário externo
  (Google/Microsoft/LDAP)

## Objetivo desta etapa
[DESCREVER AQUI qual item do backlog (ou algo novo) você quer atacar agora]

## Testes automatizados e documentação (regra permanente)

Toda funcionalidade nova implementada neste projeto, sem exceção,
deve vir acompanhada de:

1. **Teste(s) automatizado(s)** em `tests/` — mesmo que seja só
   validação estática de configuração (o projeto ainda não sobe o
   Asterisk de verdade em CI, mas isso é o próximo nível natural)
2. **Atualização do `README.md`** principal, na seção correspondente
3. **Um manual novo e numerado em `docs/`**, seguindo o padrão dos
   existentes (o que é, como configurar, como testar manualmente,
   teste automatizado correspondente, limitações conhecidas) —
   adicionado também ao índice em `docs/README.md`

Isso vale tanto para os itens do backlog acima quanto para qualquer
coisa nova que surgir. Uma funcionalidade não está "pronta" sem os
três itens acima.

Testes já existentes cobrem: transportes/criptografia do PJSIP,
contextos e hints do dialplan, docker-compose, gerador de
provisionamento, e regressão de IDs do webphone. Rodar com:
```bash
cd tests && pip install -r requirements.txt --break-system-packages && python3 -m pytest -v
```

Manuais já existentes: `docs/manual-01-core-ramais.md` até
`docs/manual-06-telefonista-web.md` (ver índice em `docs/README.md`).

## Restrições
- Manter compatível com o Docker Compose atual
- Não usar FreePBX
- Preservar a separação por tenant já existente
- Nenhuma funcionalidade nova é considerada concluída sem teste
  automatizado + README atualizado + manual em `docs/`


## Item #38 (pedido explícito do usuário, fora da numeração original do backlog): Multi-tenant completo
~~Multi-tenant completo~~ — IMPLEMENTADO. Todas as funcionalidades
construídas depois do manual 03 (fila, URA, gravação, callback,
satisfação, transferência inteligente, grupos de toque, discagem,
presença, multilíngue, painel de administração) agora funcionam pra
múltiplos tenants de verdade, via variável ${TENANT} parametrizada
(não duplicação de contexto). Encontrou e corrigiu 2 bugs de sintaxe
reais pré-existentes (ami_client.py, queue-api/server.py) - nenhum
teste pegava porque os testes de segurança liam o código como texto,
nunca importavam de verdade. Corrigido com test_module_importability.py
em todas as 7 suítes. Ver docs/manual-38.


## Item #39 (pedido explícito do usuário, novo épico): Wizard de preparação de ambiente por tenant
~~Wizard de preparação de ambiente por tenant~~ — IMPLEMENTADO. Fecha
a limitação documentada no item #38 ("adicionar tenant 3 exige editar
.conf na mão"). Painel de administração ganhou um assistente guiado
(2 passos: preencher -> revisar -> criar) que gera automaticamente:
2 telefonistas web, 3 filas (padrao/en/es), dialplan completo
([tN-internal]/[tN-hints] espelhando t1/t2), caixas de voz, e
mapeamento de DID->tenant via AstDB. Arquitetura: #include com
wildcard (pjsip_tenants/*.conf, queues_tenants/*.conf,
extensions_tenants/*.conf, voicemail_tenants/*.conf) - criar um
tenant novo NUNCA edita os arquivos estaticos de novo. Roteamento de
entrada (from-tdm-gateway) passou a consultar AstDB dinamicamente
pra DIDs nao mapeados manualmente. Ver docs/manual-39.


## Auditoria de gaps contra framework de avaliação de PABX corporativo (fornecido pelo usuário)
O usuário forneceu um framework detalhado de avaliação de PABX/contact
center (baseado nos criterios usados pra avaliar produtos contra
solucoes como as da Digitro Tecnologia). Esse framework NAO pode ser
usado pra declarar equivalencia formal com a Digitro (exigiria acesso
a documentacao proprietaria, licencas, versoes - nao disponivel).
Foi usado como CHECKLIST DE AUDITORIA INTERNA do proprio projeto,
identificando lacunas reais. Gaps encontrados, viraram novo backlog:

- #40: ~~Aviso de gravacao / conformidade LGPD~~ - IMPLEMENTADO (risco
  de conformidade mais critico encontrado - sistema gravava sem
  avisar o cliente). Ver docs/manual-40.
- #41: ~~Estacionamento de chamada (Park/Unpark)~~ - IMPLEMENTADO
  (res_parking nativo do Asterisk, vaga isolada por tenant, retorno
  automatico se nao recuperada). Ver docs/manual-41.
- #42: ~~Monitoramento de chamada (escuta/sussurro/intercalacao)~~ -
  IMPLEMENTADO (ChanSpy nativo, protegido por PIN admin-only por
  tenant, aviso explicito de implicacoes legais/trabalhistas no
  manual e na interface). Ver docs/manual-42.
- #43: ~~Sala de conferencia ad-hoc (ConfBridge)~~ - IMPLEMENTADO
  (perfis compartilhados, isolamento por tenant via nome da sala
  dinamico, ex: sala-t1-0001 vs sala-t2-0001). Ver docs/manual-43.
- #44: ~~Motivo de pausa do agente~~ - IMPLEMENTADO (QueuePause
  nativo via AMI, prioridade maxima de exibicao no painel
  operacional). Ver docs/manual-44.
- #45: ~~Overflow entre filas~~ - IMPLEMENTADO (5o parametro nativo
  do Queue(), filas de idioma transbordam pra fila geral apos
  OVERFLOW_TIMEOUT_SECONDS, sem loop). Ver docs/manual-45.
- #46: ~~SLA de fila (% atendido em N segundos)~~ - IMPLEMENTADO
  (AgentConnect/QueueCallerAbandon nativos, abandono conta contra o
  SLA mesmo com espera curta - bug real pego pelos proprios testes
  antes de chegar perto de producao). Ver docs/manual-46.

**AUDITORIA DE GAPS COMPLETA (itens #40-46)** - os 7 gaps identificados
ao comparar o projeto contra o framework de avaliacao de PABX
corporativo fornecido pelo usuario foram todos implementados: aviso
de gravacao/LGPD, estacionamento de chamada, monitoramento de
chamada, sala de conferencia ad-hoc, motivo de pausa do agente,
overflow entre filas, SLA de fila.

## Item #47: Migracao de motor STT (faster-whisper -> whisper.cpp)
Usuario pediu avaliacao de TTS/STT via Coqui TTS/XTTS. Investigacao
de licenciamento revelou: XTTS-v2 (Coqui) usa Coqui Public Model
License - PROIBE uso comercial sem licenca paga da Coqui, empresa
que encerrou operacoes em 2024, sem caminho claro pra obter essa
licenca hoje. Usuario ainda nao decidiu uso comercial vs interno -
avaliacao de TTS (Piper como padrao seguro comercialmente + XTTS
como opcional nao-comercial) ainda PENDENTE de implementacao.

STT ja estava resolvido (Whisper via faster-whisper, manual 36,
licenca MIT sem essa pegadinha) - usuario confirmou que Coqui STT
seria redundante e pediu troca de MOTOR (nao de modelo): de
faster-whisper para whisper.cpp (via pywhispercpp), mais leve pra
hardware restrito, mesma licenca MIT dos pesos do modelo Whisper nos
dois lados. ~~Migracao~~ - IMPLEMENTADA. Ver docs/manual-47.

## Item #48: TTS (Piper padrao + XTTS opcional nao-comercial) - IMPLEMENTADO (fase 1: URA)
~~TTS~~ - IMPLEMENTADO. Usuario priorizou uso na URA primeiro (depois
atendente virtual, ainda pendente). Arquitetura: ai-worker/tts_service.py
(validacao pura) + piper_engine.py (padrao, MIT) + xtts_engine.py
(opcional, TTS_XTTS_ENABLED separado de AI_FEATURES_ENABLED, nunca
liberado junto). ai-worker escreve .wav DIRETO em asterisk/sounds/custom
(volume compartilhado) - Playback(custom/nome) no dialplan ja encontra.
admin-api proxyeia POST /api/sounds/generate (admin-only) pro ai-worker.
Painel tem secao "Gerar audio por texto (TTS)", nome de arquivo
opcional (permite regenerar exatamente menu-principal-pt por texto),
escolher XTTS exige confirmacao extra na UI. Ver docs/manual-48.

## Item #49: Confirmacao falada do atendente virtual (fase 2 do TTS) - IMPLEMENTADO
~~Fase 2 (resposta falada do atendente virtual, manual 37)~~ -
IMPLEMENTADA. Apos classificar intencao, Piper sintetiza uma frase
fixa de confirmacao ("Entendi que voce quer falar sobre vendas...")
e o script AGI toca via STREAM FILE ANTES de definir INTENT_DESTINO.
Best-effort - se sintese falhar, roteamento continua normalmente sem
confirmacao (nunca bloqueia o fluxo principal). Ver docs/manual-49.

**Ambas as fases do TTS (URA + atendente virtual) agora completas.**

Outras lacunas identificadas na auditoria, nao viraram itens de
backlog ainda (fora do escopo imediato, ou exigiriam decisao adicional
do usuario, ex: integracao omnichannel/WhatsApp/chat e recursos
completos de videoconferencia): anonimizacao de dados sensiveis em
gravacao/transcricao, rate limiting em tentativas de codigo 2FA,
lista branca formal de discagem, selecao de rota por menor custo.


## Item #50: Geracao de segredos fortes antes do deploy (endurecimento de seguranca)
Usuario respondeu "sim" a pergunta sobre proximos passos - interpretado
como endurecimento de seguranca (unico dos 4 itens do roteiro que e
realmente executavel neste ambiente sandboxed, sem Asterisk real/GPU).
~~scripts/generate_secrets.py~~ - IMPLEMENTADO. Varre docker-compose.yml/
manager.conf/pjsip.conf, troca todos os placeholders "troque_esta_senha_*"
por segredos fortes de 32 caracteres, mantendo os segredos de AMI
SINCRONIZADOS entre docker-compose.yml e manager.conf. Bug real
encontrado e corrigido: "troque_esta_senha_ami" e substring de
"troque_esta_senha_ami_admin" - replace_all_placeholders ordena por
comprimento decrescente pra evitar corrupcao. Aviso explicito pra
NUNCA comitar os arquivos alterados de volta pro repositorio publico.
Nova 8a suite de testes (scripts/tests/). Ver docs/manual-50.

Tambem alertei o usuario nesta resposta: o token do GitHub usado
durante toda a conversa (github_pat_11BJXUDKQ0a2YqHZpyjiFh_...) ficou
exposto em texto claro no historico - recomendei revogar/rotacionar.

Itens do roteiro de proximos passos AINDA pendentes (nao executaveis
neste ambiente sandboxed): validacao contra Asterisk real, audios
reais em vez de placeholder (beeps), teste da IA local de verdade
(Piper/Whisper/Llama rodando de fato sem mock).


## Item #51: Script de verificacao pos-deploy - IMPLEMENTADO
Usuario disse "continuar" apos eu oferecer 2 opcoes (checklist vs
encerrar) - interpretado como "prepare o checklist/script de
verificacao". scripts/verify_deployment.py + deployment_checks.py -
3 checagens (segredos sem placeholder, login AMI real, saude dos
servicos HTTP). Nunca rodado contra ambiente real - so testado com
mocks (rede) e arquivos temporarios (secrets). Complementa mas NAO
substitui o roteiro manual de teste (manual 00) - documentado
explicitamente o que isso NAO valida (audio, roteamento de fila,
URA de ponta a ponta). Ver docs/manual-51.

**Estado do roteiro de proximos passos**: dos 4 itens originais,
2 executados neste ambiente sandboxed (#50 seguranca, #51 ferramenta
de verificacao), 2 permanecem genuinamente pendentes e exigem o
USUARIO executar num ambiente real (validacao contra Asterisk de
verdade, teste da IA local Piper/Whisper/Llama sem mock) - nao
executaveis por mim neste sandbox sem servidor real/GPU.


## Item #52: Remocao de tenant pelo wizard - IMPLEMENTADO
Usuario disse "continuar" de novo apos eu confirmar que os 2 itens
restantes do roteiro exigem ambiente real. Em vez de esperar,
escolhi fechar uma lacuna JA DOCUMENTADA (manual 39: "sem remocao de
tenant pelo wizard - so criacao") que era executavel neste sandbox.
validate_tenant_removal() (t1/t2 protegidos, tenant precisa existir),
DELETE /api/tenants/{id} (admin-only, valida ANTES de apagar arquivo,
desregistra DID, apaga os 5 arquivos de infraestrutura, recarrega
Asterisk), botao "Remover" na tabela do wizard com confirmacao. Ver
docs/manual-52.

814 testes, 52 manuais, 8 suites - tudo passando e no GitHub.


## Item #53: Lista de audios existentes no painel - IMPLEMENTADO
Usuario disse "seguir" mais uma vez sem direcao nova. Continuei o
padrao de fechar lacunas ja documentadas nos manuais (mais
sustentavel que ficar sugerindo indefinidamente). Fechada a lacuna
do manual 48 ("sem lista de audios gerados na interface").
admin-api/sounds.py (list_sound_files, lista .wav com metadados,
mais recente primeiro), GET /api/sounds (admin+supervisor, leitura),
tabela na secao de TTS do painel, recarrega apos gerar audio novo.
Ver docs/manual-53.

823 testes, 53 manuais, 8 suites - tudo passando e no GitHub.

NOTA para proxima interacao: se o usuario disser "continuar"/"seguir"
de novo SEM direcao nova, considerar perguntar explicitamente que
area ele quer que eu foque, em vez de continuar escolhendo pequenas
lacunas sozinho indefinidamente - o projeto já esta maduro (53
manuais) e pode ser hora de uma direcao mais deliberada do usuario.


## Item #54: Limpeza de ramais orfaos ao remover tenant - IMPLEMENTADO
Usuario confirmou explicitamente via ask_user_input: "Continuar
fechando pequenas lacunas dos manuais (eu escolho)". Fechei a lacuna
do proprio manual 52 (que eu escrevi na resposta anterior): ramais
dinamicos criados dentro de um tenant nao eram limpos ao remover o
tenant inteiro. store.py ganhou delete_extensions_by_tenant() (4
testes), _handle_remove_tenant agora tambem apaga os 3 arquivos
dinamicos de ramais (dial/hints/voicemail) e os registros orfaos no
extensions_store.json. Interface informa quantos ramais foram
limpos junto. Ver docs/manual-54.

829 testes, 54 manuais, 8 suites - tudo passando e no GitHub.


## Item #55: Monitoramento de chamada estendido a ramais dinamicos - IMPLEMENTADO
Continuando a fechar lacunas (usuario confirmou essa direcao).
Fechada a limitacao do manual 42 ("so cobre as telefonistas
1010/1011"). admin-api ganhou ami_client.register_extension_mapping/
unregister_extension_mapping (AstDB familia extension-map-{tenant}),
sincronizado em create/update/delete de ramal via
regenerate_and_reload(extra_ami_action=...) reaproveitando a mesma
conexao AMI. Dialplan [chamada-monitorada] consulta
DB(extension-map-${TENANT}/${MONITOR_TARGET}) como fallback pra
qualquer numero alem de 1010/1011. Limitacao aceita: numero antigo
nao e limpo se o numero do ramal mudar numa edicao (so o novo e
registrado). Ver docs/manual-55.

833 testes, 55 manuais, 8 suites - tudo passando e no GitHub.


## Item #56: Overflow entre filas configuravel por tenant - IMPLEMENTADO
Fechada a lacuna do manual 45 ("sem interface no painel pra ajustar
o valor"). admin-api ganhou overflow.py (validacao 5-600s),
ami_client.set_overflow_timeout/get_overflow_timeout (este ultimo
via DBGetTree, nao DBGet simples, ja que precisamos do VALOR
numerico, nao so confirmacao sim/nao - diferenca tecnica importante
documentada no manual). Dialplan (t1/t2-internal + template do
wizard) consulta DB(config-${TENANT}/overflow-timeout-segundos) com
fallback pro OVERFLOW_TIMEOUT_SECONDS global (45s). Interface no
painel, secao "Overflow entre filas", tenant-aware. Ver docs/manual-56.

849 testes, 56 manuais, 8 suites - tudo passando e no GitHub.


## Item #57: Historico de tempo em pausa por motivo - IMPLEMENTADO
Fechada a lacuna do manual 44 ("sem relatorio historico de tempo em
pausa por motivo"). agent_pause.py ganhou PauseHistoryStore (JSONL,
mesmo padrao de survey.py/reports.py) + AgentPauseStore agora grava
um registro completo quando o agente DESPAUSA (unico momento em que
a duracao e conhecida). Honestidade tecnica: despausar sem pausa
anterior conhecida (ex: queue-api reiniciou no meio de uma pausa) nao
grava nada - nao inventa duracao. GET /api/reports/pauses (by_reason,
by_extension). Painel operacional mostra secao nova, ordenada por
tempo decrescente, em minutos. Ver docs/manual-57.

864 testes, 57 manuais, 8 suites - tudo passando e no GitHub.


## Item #58: Historico de SLA por dia - IMPLEMENTADO
Fechada a lacuna do manual 46 ("sem historico - snapshot() sempre do
dia atual"). QueueSLATracker ganhou history_store opcional (mesmo
padrao JSONL de agent_pause.py/survey.py) - persiste o resumo do dia
ANTES de resetar a meia-noite. Fila sem chamada oferecida (offered=0)
nao gera registro vazio. GET /api/metrics/sla/history (by_date).
Armadilha de rota evitada e testada: "/api/metrics/sla/history"
comeca com "/api/metrics/sla" - checagem especifica precisa vir
ANTES da generica no do_GET, senao startswith() faria cair na rota
errada. Ver docs/manual-58.

876 testes, 58 manuais, 8 suites - tudo passando e no GitHub.


## Item #59: Interface do historico de SLA no painel - IMPLEMENTADO
Fechada a lacuna do proprio manual 58 ("sem interface no painel
ainda"). Secao nova no painel operacional, renderSlaHistory() -
mostra dias fechados (mais recente primeiro) com % de SLA por fila.
Bug de teste real encontrado: "renderSla" e prefixo de
"renderSlaHistory", e como a nova funcao ficou definida ANTES da
antiga no arquivo, buscas por substring passaram a achar a funcao
errada primeiro - corrigido tornando a busca mais especifica
("function renderSla(" com parentese). Ver docs/manual-59.

879 testes, 59 manuais, 8 suites - tudo passando e no GitHub.


## Item #60: Reproducao de audio na lista do painel - IMPLEMENTADO
Fechada a lacuna do manual 53 ("sem reproducao de audio na
interface"). Problema real descoberto: <audio src="..."> nao manda
header Authorization, entao API responderia 401 - solucao foi
fetch() manual com o token, pedindo blob, criando URL temporaria via
URL.createObjectURL() e tocando num <audio> compartilhado oculto.
admin-api/sounds.py ganhou is_safe_sound_filename() (protecao contra
path traversal, ex: ../../etc/passwd) - validada ANTES de tocar no
sistema de arquivos. GET /api/sounds/<filename> serve o wav puro
(admin+supervisor). Ver docs/manual-60.

890 testes, 60 manuais, 8 suites - tudo passando e no GitHub.
