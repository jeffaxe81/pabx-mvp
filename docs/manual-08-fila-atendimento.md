# Manual 08 — Fila de atendimento (backlog #2)

## O que é
Chamadas que chegam sem ramal específico (via gateway TDM, ou pela
extensão de teste `800`) entram numa fila. Se a telefonista está
livre, toca direto nela. Se está ocupada, a chamada espera (com
música de espera) — e aparece num painel na interface web, onde a
telefonista pode **escolher qual chamada específica atender**, não
só a primeira da fila.

## Por que precisou de uma peça nova (queue-api)
O Asterisk não expõe "quem está esperando numa fila" via SIP/WebRTC —
isso só existe via **AMI** (Asterisk Manager Interface), um protocolo
de gerenciamento à parte. Por isso existe `queue-api/`: um serviço
Python pequeno (sem dependências externas, só biblioteca padrão) que:
1. Conecta no AMI do Asterisk e escuta eventos de fila
   (`QueueCallerJoin`/`QueueCallerLeave`)
2. Mantém em memória quem está esperando, em cada fila
3. Expõe isso como uma API HTTP simples (`GET /api/queue`) que o
   webphone consulta a cada 3 segundos
4. Quando a telefonista clica "Atender" numa chamada específica,
   chama `POST /api/queue/pickup`, que executa uma ação AMI
   `Redirect` — tira aquele canal específico da fila e manda ele
   direto pro ramal da telefonista (contexto `pickup-target` no
   dialplan)

## Como configurar
1. `asterisk/manager.conf` — habilita AMI na porta `5038`, cria o
   usuário `queue-api` (**troque a senha padrão**)
2. `asterisk/queues.conf` — define a fila `fila-t1`, com
   `t1-recepcao` como único membro
3. `asterisk/extensions.conf` — chamadas sem DID mapeado (e a
   extensão de teste `800`) entram em `Queue(fila-t1)`; o contexto
   `[pickup-target]` é usado só pelo Redirect da AMI
4. `docker-compose.yml` — serviço `queue-api`, com as mesmas
   credenciais AMI de `manager.conf` nas variáveis de ambiente
   (**mantenha os dois sincronizados** — há um teste automatizado que
   verifica isso)
5. No webphone, o campo "API da fila" na tela de conexão aponta pro
   endereço do `queue-api` (porta `8090`)

## Como testar manualmente
1. `docker compose up -d`
2. Conecte a telefonista web normalmente (ramal `t1-recepcao`)
3. De **outro** ramal, disque `800` — simula uma chamada entrando na
   fila
4. Se a telefonista estiver livre, deve tocar direto nela (fila com 1
   membro livre = toca automaticamente)
5. Para testar o pickup dirigido: com a telefonista **ocupada** em
   outra chamada, disque `800` de um terceiro ramal — a chamada deve
   aparecer no painel "Fila de espera" da interface web, com o tempo
   de espera contando
6. Clique "Atender" nessa chamada da fila — ela deve tocar na
   interface web como uma chamada recebida normal

## Teste automatizado
- `queue-api/tests/test_ami_protocol.py` — parsing do protocolo AMI
  (sem precisar de socket/rede)
- `queue-api/tests/test_queue_state.py` — lógica de entrar/sair da
  fila, ordenação, limpeza por Hangup
- `tests/test_ami_config.py` — `manager.conf`/`queues.conf` consistentes
- `tests/test_extensions_conf.py::test_pickup_target_context_dials_receptionist`
- `tests/test_docker_compose.py::test_queue_api_env_matches_manager_conf_credentials`
- `tests/test_webphone_html.py::test_queue_pickup_sends_channel_to_correct_endpoint`

## Limitações conhecidas (honestidade técnica)
- **O cliente AMI real (`queue-api/ami_client.py`) não tem teste de
  integração** — só dá pra validar contra um Asterisk de verdade
  rodando, igual ao tronco TDM (manual 04). Os testes automatizados
  cobrem o parsing do protocolo e a lógica de estado, que são a parte
  determinística e testável sem rede
- Só existe fila para o tenant 1 (`fila-t1`); replicar o padrão para o
  tenant 2 segue a mesma lógica de `t2-` já usada em outras partes do
  projeto
- `queue-api` não tem autenticação própria na API HTTP (qualquer um
  na rede que alcançar a porta 8090 pode listar a fila e puxar
  chamadas) — aceitável para uso interno numa rede confiável, mas
  precisa de camada de auth antes de expor além disso
- CORS está liberado para qualquer origem (`*`) — apertar isso é
  trivial (trocar por uma allowlist), só não fiz porque o MVP roda
  tudo na mesma rede local
