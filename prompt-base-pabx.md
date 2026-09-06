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
6. Discagem por clique a partir do CRM (click-to-call)
7. Dashboard de métricas do dia (volume, TMA, taxa de perdidas) por
   tenant
8. Múltiplas telefonistas simultâneas com roteamento round-robin das
   chamadas de entrada
9. PWA instalável com notificação nativa (tocar mesmo em segundo
   plano/tela bloqueada)
10. Painel de administração web para cadastro de ramais/tenants (hoje
    é tudo manual editando os arquivos `.conf`)

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
