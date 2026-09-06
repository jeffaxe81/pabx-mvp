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
19. Controle de permissões e perfis (admin/supervisor/atendente) -
    pré-requisito natural do painel de administração (item 10)
20. Autenticação em dois fatores para o painel de administração

**Fase 3 — Diferenciais e IA (novo)**
21. Transcrição automática de chamadas
22. Resumo automático de chamada com identificação de tarefas
23. Análise de sentimento (detectar insatisfação/urgência)
24. Atendente virtual com IA (primeira camada de triagem)
25. Discador automático para campanhas (outbound em massa)
26. Chamada de retorno (callback) sem permanecer na fila
27. Pesquisa de satisfação pós-atendimento
28. Transferência inteligente por regra (horário/cliente/assunto)
29. Presença corporativa avançada (ausente/reunião/férias) com
    sincronização de calendário
30. Atendimento multilíngue

**Infraestrutura e segurança (novo)**
31. Lista de bloqueio (números/DDIs/anônimas)
32. Detecção de fraude (alerta de volume anormal, limite de gasto)
33. Alta disponibilidade e backup automático (hoje é container único,
    sem failover)
34. Monitoramento de qualidade de chamada (jitter/latência/perda de
    pacotes)

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
