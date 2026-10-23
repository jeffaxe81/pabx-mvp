# PABX Open Source (SIP) - Asterisk + PJSIP

MVP evoluído: chamadas criptografadas, multi-tenant, tronco para
gateway TDM e auto-provisionamento de telefones.

## Estrutura

```
pabx-mvp/
├── docker-compose.yml
├── asterisk/
│   ├── pjsip.conf        # transportes, templates, ramais por tenant, tronco TDM
│   ├── extensions.conf   # dialplan (contextos isolados por tenant)
│   ├── voicemail.conf    # caixas de mensagem por tenant
│   ├── rtp.conf
│   └── certs/            # certificado TLS (self-signed, trocar em produção)
│       ├── asterisk.crt
│       └── asterisk.key
└── provisioning/
    ├── devices.json       # cadastro MAC -> ramal
    ├── generate.py        # gera os arquivos de config por MAC
    ├── templates/         # templates por fabricante (yealink.cfg.tpl, ...)
    └── files/             # arquivos gerados, servidos via HTTP
```

## 1. Chamadas criptografadas (SRTP + TLS)

- Sinalização SIP trafega por **TLS na porta 5061** (em vez de UDP puro)
- Áudio trafega criptografado via **SRTP** (`media_encryption=sdes`)
- Os ramais usam o template `endpoint-secure`, que já aplica os dois
- Certificado incluído é **self-signed**, apenas para desenvolvimento.
  Em produção, troque por um certificado válido (Let's Encrypt, CA
  interna da empresa, etc.) em `asterisk/certs/`.

No softphone, configure a conta como **TLS** (não UDP/TCP) e ative
"SRTP obrigatório" nas opções avançadas (Zoiper: Account → Advanced →
Encryption).

## 2. Multi-tenant

Cada empresa/cliente tem seu próprio contexto isolado no dialplan:

- `t1-internal` → Tenant 1 (ramais `t1-1001`, `t1-1002`)
- `t2-internal` → Tenant 2 (ramal `t2-1001`)

Um tenant **não enxerga nem consegue discar** para ramais do outro,
mesmo que a numeração se repita (ambos podem ter um "1001").

Para adicionar um novo tenant:
1. Duplique o bloco de ramais em `pjsip.conf` com prefixo `t3-`
2. Crie o contexto `t3-internal` em `extensions.conf`
3. Adicione a seção `[t3]` em `voicemail.conf`

Isso ainda é uma separação **lógica** (mesmo Asterisk, mesmo dialplan
engine). Para isolamento mais forte (billing separado, cada tenant com
seu próprio painel), o próximo passo seria uma camada de API/DB na
frente do Asterisk controlando tudo via AMI/ARI — fora do escopo deste
MVP.

## 3. Tronco para gateway TDM

O Asterisk não fala TDM diretamente (a menos que você use hardware
Digium/Sangoma com placas E1/T1 físicas dentro do servidor). O caminho
padrão de mercado é:

```
Linha TDM (analógica/E1/T1) → Gateway (Grandstream GXW, AudioCodes
MP-11x, Patton SmartNode) → converte para SIP → Asterisk
```

Do lado do Asterisk, o gateway aparece como **mais um endpoint SIP**
(seção `gateway-tdm` no `pjsip.conf`). Ajuste:

- `match=192.168.1.200` → IP real do gateway na sua rede
- Os DIDs em `[from-tdm-gateway]` (`extensions.conf`) → números reais
  que chegam pela linha TDM, mapeados para o tenant correto

Chamadas de saída: qualquer ramal disca `0` + número
(ex: `01140028922`) e a chamada sai pelo tronco TDM.

## 4. Auto-provisionamento

Fluxo:
1. Cadastre o telefone (MAC, ramal, senha) em `provisioning/devices.json`
2. Rode `python3 provisioning/generate.py` → gera `provisioning/files/<MAC>.cfg`
3. O telefone físico, ao ser configurado para buscar provisionamento em
   `http://<ip-do-servidor>:8080/`, baixa seu arquivo automaticamente
   pelo MAC e já sobe configurado (conta SIP, senha, TLS, SRTP)

Hoje só existe template para **Yealink**. Para outro fabricante
(Grandstream, Cisco, Snom...), crie um novo arquivo em
`provisioning/templates/` seguindo o formato do fabricante e mapeie em
`TEMPLATE_EXT` dentro de `generate.py`.

> Nota: cada fabricante tem um mecanismo de "descoberta" diferente do
> servidor de provisionamento (DHCP option 66, PnP multicast, ou
> configuração manual da URL no aparelho). Isso é configurado no
> telefone físico, fora do escopo deste repositório.

## Como rodar

```bash
cd pabx-mvp
python3 provisioning/generate.py   # gera os arquivos de provisionamento
docker compose up -d
```

Serviços expostos:
- `5060/udp` — SIP sem criptografia (compatibilidade/testes)
- `5061/tcp` — SIP com TLS
- `10000-10200/udp` — RTP (mídia de áudio)
- `8080/tcp` — servidor de provisionamento

## Testando

1. Registre um softphone como `t1-1001` via **TLS**, servidor `<ip>:5061`
2. Disque `1002` → toca no outro ramal do mesmo tenant
3. Disque `600` → teste de eco (confirma SRTP funcionando)
4. Registre outro softphone como `t2-1001` e confirme que ele **não**
   consegue discar `1002` (não existe nesse tenant)

```bash
docker exec -it pabx-mvp asterisk -rvvv
pjsip show endpoints
pjsip show transports    # confirma que a porta 5061/TLS está ativa
```

## 5. Telefonista direto no navegador (WebRTC)

Interface web em `webphone/index.html` — a recepcionista atende e faz
chamadas sem instalar nada, direto do Chrome/Firefox.

Como funciona:
- Ramal dedicado `t1-recepcao` (número `1000`), configurado com
  `webrtc=yes` no PJSIP (DTLS-SRTP + ICE)
- O Asterisk expõe um WebSocket seguro (WSS) na porta `8089`,
  habilitado em `asterisk/http.conf`
- A página conecta nesse WSS usando a biblioteca **JsSIP**

Rodando:
```bash
docker compose up -d
```
Acesse `http://<ip-do-servidor>:8082` e conecte com:
- **Servidor**: `wss://<ip-do-servidor>:8089/ws`
- **Ramal**: `t1-recepcao`
- **Senha**: a definida em `pjsip.conf` (troque o valor padrão!)

> **Atenção**: o certificado é self-signed. O navegador vai bloquear a
> conexão WSS até você abrir `https://<ip-do-servidor>:8089` uma vez e
> aceitar manualmente o aviso de certificado inválido — assim ele passa
> a confiar na mesma origem para o WebSocket. Em produção, use um
> certificado válido (Let's Encrypt) e esse passo manual some.
>
> Ligações que chegam sem ramal identificado (`from-tdm-gateway`) agora
> caem direto no ramal 1000 — a telefonista faz o papel de recepção.

O que a interface já faz: discar, atender, recusar, mudo, espera,
transferência cega e histórico de chamadas da sessão. **Também mostra em
tempo real quais colegas estão livres, tocando ou em chamada** (BLF via
SIP SUBSCRIBE aos hints do Asterisk) — clique num colega da lista para
ligar direto pra ele, ou para transferir a chamada atual na hora.
**E agora também transferência assistida** (consulta antes de
completar) — ver `docs/manual-07-transferencia-assistida.md` para o
fluxo completo e uma ressalva técnica importante sobre como a troca é
percebida pelo cliente.

**E fila de atendimento com pickup dirigido**: chamadas sem ramal
específico esperam numa fila, visível em tempo real no painel "Fila
de espera" da interface — a telefonista escolhe qual chamada atender
(não só a mais antiga). Requer o serviço `queue-api` (fala AMI com o
Asterisk) — ver `docs/manual-08-fila-atendimento.md`.

**E gravação automática de chamadas** com player embutido na
interface (painel "Gravações") — ver `docs/manual-09-gravacao-chamadas.md`,
inclusive um aviso importante sobre indicação legal de gravação pro
cliente.

**E multi-chamada (2 linhas simultâneas)**: uma segunda chamada
chegando não é mais recusada — a telefonista pode atendê-la (a
primeira vai pra espera automaticamente) e alternar entre as duas —
ver `docs/manual-10-multi-chamada.md`.

**E notificação de chamada perdida** (e-mail/WhatsApp, desligado por
padrão até você configurar credenciais reais) — ver
`docs/manual-11-notificacao-chamada-perdida.md`.

**E discagem por clique a partir do CRM**: um sistema externo chama
uma API pra disparar ligação (liga primeiro pra telefonista, depois
completa pro cliente) — protegida por chave de API, desligada por
padrão — ver `docs/manual-12-click-to-call.md`.

**E dashboard de métricas do dia** (painel "Métricas de hoje" no
webphone): chamadas totais, atendidas, perdidas, TMA e taxa de
perdidas, calculados a partir do CDR do Asterisk — ver
`docs/manual-13-dashboard-metricas.md`.

**E múltiplas telefonistas simultâneas**: duas (ou mais) operadoras
logadas ao mesmo tempo, com a fila distribuindo chamadas em
round-robin entre elas, e o pickup dirigido sabendo pra qual delas
mandar cada chamada puxada — ver `docs/manual-14-multiplas-telefonistas.md`.

**E PWA instalável com notificação nativa**: a interface pode ser
instalada como app, toca campainha de verdade e mostra notificação do
sistema operacional em chamadas recebidas — mesmo com a aba em
segundo plano — ver `docs/manual-15-pwa-notificacao.md`.

**E painel de administração web**: cadastro de ramais do tenant 1
(criar, editar, excluir) via navegador, sem editar `.conf` na mão — o
Asterisk recarrega sozinho via AMI. Login desligado por padrão até
configurar uma senha de admin — ver `docs/manual-16-painel-administracao.md`.

**E painel operacional consolidado** (`webphone/painel-operacional.html`):
fila, estado dos ramais e métricas do dia numa tela só, pra supervisão —
ver `docs/manual-17-painel-operacional.md`.

**E relatórios históricos** por atendente e tenant, com filtro de
período — diferente das métricas do dia (que zeram à meia-noite), fica
persistido em disco — ver `docs/manual-18-relatorios.md`.

**E screen-pop pro CRM** (PABX→CRM): link clicável na interface + webhook
opcional do servidor, avisando quem está ligando assim que a chamada
começa a tocar — ver `docs/manual-19-crm-screen-pop.md`.

**E regras de discagem externa**: bloqueio de números via AstDB
(gerenciável pelo painel de administração), rota alternativa por
prefixo, segundo tronco (`gateway-tdm-2`) — ver `docs/manual-20-discagem-externa.md`.

**E busca de gravações por número/atendente/período**, com expurgo
automático configurável (desligado por padrão) — ver
`docs/manual-21-busca-retencao-gravacoes.md`.

**E e-mail de correio de voz**: mensagem de voz chega por e-mail com
áudio anexado, via um pequeno script relay (o Asterisk não tem MTA
próprio) — ver `docs/manual-22-email-correio-voz.md`.

**E URA (menu de voz)**: modo feriado com prioridade sobre horário
comercial, roteamento por dígito — com áudio placeholder (beep) até
você trocar por gravação real — ver `docs/manual-23-ura.md`.

**E grupos de toque**: dois exemplos prontos, simultâneo (`900`) e em
sequência (`901`), pra quando fila é over-engineering — ver
`docs/manual-24-grupos-de-toque.md`.

**E permissões e perfis** no painel de administração: dois papéis
(admin/supervisor), com o backend checando permissão antes de
qualquer mutação — ver `docs/manual-25-permissoes-perfis.md`.

**E autenticação em dois fatores (2FA)**: TOTP autoatendimento (cada
usuário protege a própria conta), implementação validada contra o
vetor de teste oficial do RFC 6238 — ver `docs/manual-26-2fa.md`.

Com isso, a **Fase 2 do backlog está completa**.

**E detecção de fraude**: alerta de volume anormal de chamadas
externas, bloqueio automático de destino suspeito (reaproveitando a
lista de bloqueio existente) e limite de gasto diário por ramal — ver
`docs/manual-27-deteccao-fraude.md`.

**E backup automático** (não é alta disponibilidade de verdade — ver
o aviso honesto logo no início do manual): empacota configuração e
dados de negócio diariamente, com procedimento de restauração
documentado — ver `docs/manual-28-backup-disponibilidade.md`.

**E monitoramento de qualidade de chamada**: jitter, perda de pacotes
e RTT capturados via RTCP nas chamadas da telefonista, com alerta
automático — ver `docs/manual-29-monitoramento-qualidade.md`.

Com isso, os **itens de infraestrutura do backlog (31-34) estão
completos** — resta a Fase 3 (recursos de IA/ML).

**E discador automático (campanhas)**: lista de contatos, controle de
tentativas, reaproveitando o mesmo mecanismo do click-to-call — ver
`docs/manual-30-discador-campanhas.md`.

**E chamada de retorno (callback)**: opção 9 na URA — o cliente deixa
o número, e o sistema liga de volta (fila FIFO) quando um atendente
está livre — ver `docs/manual-31-callback.md`.

**E pesquisa de satisfação pós-atendimento**: o cliente permanece na
linha depois que o atendente desliga (via opção `c`/`g` do
Asterisk) e responde uma nota de 1 a 5, associada ao atendente que
participou da chamada — ver `docs/manual-32-pesquisa-satisfacao.md`.

**E transferência inteligente por regra**: cliente VIP identificado
pelo número roteia direto pro ramal escolhido (prioridade máxima), e
retorno automático de verdade pra fila geral quando ninguém atende —
ver `docs/manual-33-transferencia-inteligente.md`.

**E presença corporativa avançada**: cada telefonista marca
manualmente ausente/em reunião/férias (com nota), sobrepondo o BLF
automático nos painéis — sincronização com calendário fica fora do
escopo (mesma categoria dos itens de IA) — ver `docs/manual-34-presenca-avancada.md`.

**E atendimento multilíngue**: seleção de idioma na URA (português/
inglês/espanhol), com fila e menu de áudio próprios pra cada um — ver
`docs/manual-35-multilingue.md`.

Com isso, **toda a Fase 3 sem dependência de IA está completa**.

**E, fechando o backlog inteiro: transcrição, resumo automático,
análise de sentimento e atendente virtual com IA** — usando modelos
**locais** (Whisper + Llama 3 via Ollama), sem nuvem, sem custo por
requisição. Esta é a primeira parte do projeto com dependência
externa real e sem teste de integração de verdade (sem GPU/modelos
disponíveis no ambiente onde foi construído) — ver os avisos de
honestidade técnica logo no início de `docs/manual-36-transcricao-resumo-sentimento.md`
e `docs/manual-37-atendente-virtual.md`.

**E, por fim, multi-tenant completo**: toda funcionalidade construída
depois do manual 03 (fila, URA, gravação, callback, satisfação,
transferência inteligente, grupos de toque, discagem, presença,
multilíngue, painel de administração) agora funciona pra múltiplos
tenants de verdade, não só o tenant 1 — usando uma variável
`${TENANT}` parametrizada em vez de duplicar contexto por contexto.
Esse trabalho também encontrou e corrigiu dois bugs de sintaxe reais
pré-existentes (`ami_client.py` e `queue-api/server.py`), fechados com
um novo teste de importabilidade em todas as suítes — ver
`docs/manual-38-multi-tenant-completo.md`.

**E um wizard de preparação de ambiente por tenant**: cria telefonistas,
filas, dialplan completo e mapeamento de DID pra um tenant novo (t3,
t4...) sem editar nenhum `.conf` na mão — usando `#include` com
wildcard nos arquivos estáticos — ver `docs/manual-39-wizard-tenant.md`.

**E, a partir de uma auditoria de gaps contra um framework de avaliação
de PABX corporativo**: aviso de gravação em conformidade com a LGPD,
tocando antes de qualquer chamada ser gravada, nos dois tenants e em
qualquer tenant criado pelo wizard a partir de agora — ver
`docs/manual-40-aviso-gravacao-lgpd.md`. Essa auditoria identificou
outras lacunas reais (estacionamento de chamada, monitoramento de
chamada/escuta-sussurro-intercalação, conferência ad-hoc, motivo de
pausa de agente, overflow entre filas, SLA de fila) que seguem como
próximos itens do backlog.

**E estacionamento de chamada**: usando o módulo nativo `res_parking`
do Asterisk, com vaga isolada por tenant (inclusive nos criados pelo
wizard) e retorno automático se ninguém recuperar — ver
`docs/manual-41-estacionamento-chamada.md`.

**E monitoramento de chamada** (escuta silenciosa/sussurro/
intercalação): protegido por PIN admin-only por tenant, com aviso
explícito sobre implicações legais e trabalhistas — vigilância de
conversa de terceiros exige mais do que só ser tecnicamente possível.
Ver `docs/manual-42-monitoramento-chamada.md`.

**E sala de conferência ad-hoc** (`ConfBridge`): diferente do grupo de
toque, aqui várias pessoas conversam ao mesmo tempo de verdade, com
isolamento por tenant garantido pelo próprio nome da sala — ver
`docs/manual-43-sala-conferencia.md`.

**E motivo de pausa do agente**: `QueuePause` nativo do Asterisk, com
o painel de supervisão mostrando o motivo exato (não só
"indisponível"), prioridade máxima de exibição por ser o estado mais
operacional — ver `docs/manual-44-motivo-pausa-agente.md`.

**E overflow entre filas**: se a fila de idioma específico (inglês/
espanhol) não atender dentro de um tempo configurável, a chamada
transborda automaticamente pra fila geral do tenant — ver
`docs/manual-45-overflow-filas.md`.

**E SLA de fila** (% atendido dentro de N segundos): fecha os sete
gaps identificados na auditoria contra o framework de avaliação de
PABX corporativo (itens #40-46) — ver `docs/manual-46-sla-fila.md`.

**E síntese de voz (TTS)**: motor de transcrição migrado pra
`whisper.cpp` (mais leve, sem GPU) — ver
`docs/manual-47-migracao-whisper-cpp.md`. TTS ganhou dois motores
desacoplados: Piper (padrão, MIT, seguro comercialmente) e XTTS-v2
(opcional, desligado por padrão — licença não-comercial da Coqui,
empresa que encerrou operações em 2024). Admin gera áudio de anúncios
da URA digitando o texto, sem precisar de locutor — ver
`docs/manual-48-tts-piper-xtts.md`.

**E, fechando a fase 2**: o atendente virtual com IA (manual 37)
agora confirma em voz o que entendeu antes de transferir a chamada
("Entendi que você quer falar sobre vendas...") — best-effort, nunca
bloqueia o roteamento se a síntese falhar — ver
`docs/manual-49-confirmacao-falada-atendente-virtual.md`.

**E, por fim, um script de geração de segredos fortes**: as senhas
placeholder do repositório são públicas (qualquer pessoa que veja o
código no GitHub sabe essas senhas) — `scripts/generate_secrets.py`
troca todas de uma vez, mantendo os segredos de AMI sincronizados
entre `docker-compose.yml` e `manager.conf`, com aviso explícito pra
nunca comitar o resultado de volta pro repositório público. Ver
`docs/manual-50-geracao-segredos.md`.

**E um script de verificação pós-deploy**: checa mecanicamente (AMI,
serviços HTTP, ausência de senha placeholder) o que dá pra confirmar
programaticamente depois de subir num ambiente real — não substitui
testar uma chamada de verdade, complementa o roteiro de implantação
— ver `docs/manual-51-verificacao-pos-deploy.md`.

**E, fechando uma lacuna documentada desde o manual 39**: remoção de
tenant pelo wizard — antes só criava, agora também apaga toda a
infraestrutura gerada (dialplan, telefonistas, filas, vaga de
estacionamento) e desregistra o DID, protegendo os exemplos estáticos
t1/t2 de remoção acidental — ver `docs/manual-52-remocao-tenant.md`.

**E lista de áudios existentes no painel**: fecha outra lacuna
documentada (manual 48) — a seção de TTS agora mostra todo `.wav`
existente em `asterisk/sounds/custom/`, com nome, tamanho e data,
atualizando automaticamente após gerar um áudio novo — ver
`docs/manual-53-lista-audios.md`.

**E, fechando outra lacuna documentada no próprio manual 52**:
remover um tenant agora também limpa os ramais dinâmicos criados
dentro dele (arquivos e registros), evitando ramais "fantasma"
listados pra um tenant que não existe mais — ver
`docs/manual-54-limpeza-ramais-orfaos.md`.

**E, fechando a última lacuna documentada no manual 42**: o
monitoramento de chamada agora alcança qualquer ramal dinâmico
criado pelo painel, não só as telefonistas fixas — o `admin-api`
sincroniza um mapeamento número→endpoint no AstDB toda vez que um
ramal é criado, editado ou removido — ver
`docs/manual-55-monitoramento-ramais-dinamicos.md`.

**E, fechando a lacuna do manual 45**: overflow entre filas agora é
configurável por tenant direto pelo painel (5-600 segundos), com
fallback pro valor padrão global quando não configurado — ver
`docs/manual-56-overflow-por-tenant.md`.

**E, fechando a lacuna do manual 44**: histórico de tempo em pausa
por motivo — cada vez que um agente despausa, o tempo completo é
gravado (JSONL, mesmo padrão de survey.py/reports.py), agregado por
motivo e por ramal no painel operacional — ver
`docs/manual-57-historico-pausa.md`.

**E, fechando a última lacuna documentada no manual 46**: histórico
de SLA por dia — persistido automaticamente à meia-noite (fila sem
chamada não polui o histórico), consultável por
`GET /api/metrics/sla/history` — ver `docs/manual-58-historico-sla.md`.

**E, fechando essa mesma lacuna de vez**: o histórico de SLA agora
também aparece direto no painel operacional, não só via API — ver
`docs/manual-59-interface-historico-sla.md`.

**E, fechando a lacuna do manual 53**: a lista de áudios do painel
agora reproduz o som direto na interface (via `fetch()` autenticado +
blob, já que `<audio src>` não manda o token exigido pela API), com
proteção explícita contra path traversal — ver
`docs/manual-60-reproducao-audio.md`.

**E, fechando a última limitação daquele mesmo item**: as URLs de
objeto do player de áudio agora são revogadas antes de criar a
próxima, evitando o vazamento de memória apontado no manual anterior
— ver `docs/manual-61-correcao-vazamento-audio.md`.

**E, fechando a última lacuna documentada no manual 55**: renumerar
um ramal dinâmico agora limpa o mapeamento de monitoramento antigo
automaticamente, não só registra o novo — ver
`docs/manual-62-limpeza-renumeracao.md`.

**E, fechando as duas últimas lacunas de relatório do projeto**:
filtro de intervalo de datas (`?start=`/`?end=`) no histórico de
pausa e no histórico de SLA, com interface no painel operacional que
sobrevive ao polling automático — ver
`docs/manual-63-filtro-data-relatorios.md`.

**E, integrando o atendente virtual (STT+LLM+TTS) direto no fluxo
real de atendimento**: o menu principal da URA ganhou a opção `0`
("fale com um assistente"), reaproveitando a pipeline dos manuais
37/49 em vez de deixá-la isolada numa extensão de teste. Durante essa
integração, um bug real de conformidade foi encontrado e corrigido: o
atendente virtual gravava a voz do cliente sem nunca tocar o aviso de
gravação exigido pela LGPD (manual 40) — ver
`docs/manual-64-integracao-voz-ura.md`.

**E, pra quem está rodando isso a partir do Windows**: um manual
explicando por que `network_mode: host` (usado por `asterisk`,
`queue-api` e `admin-api`, necessário pro SIP/RTP funcionar com NAT)
não funciona como esperado no Docker Desktop pra Windows, e como
contornar isso com Docker Engine nativo dentro do WSL2 — ver
`docs/manual-65-windows-wsl2.md`.

Para ajustar quais ramais aparecem na lista de colegas, edite o array
`COLLEAGUES` no início do `<script>` em `webphone/index.html`. Cada
ramal monitorado precisa ter um `hint` correspondente em
`extensions.conf` (contexto `t1-hints` / `t2-hints`).

O que **não** faz (de propósito, é MVP): múltiplas chamadas
simultâneas, gravação, transferência assistida com consulta — ver
ideias abaixo.

## Testes automatizados

Duas suítes:

```bash
# suíte principal (configs do Asterisk, docker-compose, webphone)
cd tests
pip install -r requirements.txt --break-system-packages
python3 -m pytest -v

# suíte do queue-api (parsing AMI e lógica de fila, sem rede)
cd ../queue-api
python3 -m pytest tests/ -v
```

Testes estáticos distribuídos em 8 suítes (`tests/`, `queue-api/tests/`,
`admin-api/tests/`, `asterisk/scripts/tests/`, `backup/tests/`,
`ai-worker/tests/`, `asterisk/agi/tests/`, `scripts/tests/`) —
nenhuma delas sobe o Asterisk, Whisper ou Ollama de verdade. Detalhes
em `tests/README.md`.

## Documentação

Um manual por funcionalidade em `docs/` (o que é, como configurar,
como testar manualmente, limitações conhecidas). Índice completo em
`docs/README.md`.

## Próximos passos

- TLS com certificado válido (não self-signed) em produção
- Fila de atendimento por tenant (`queues.conf`)
- URA (IVR) por tenant
- Painel web para cadastro de ramais/tenants (hoje é tudo manual nos
  arquivos `.conf`)
- Suporte a mais fabricantes no auto-provisionamento


## Qualidade e integração contínua

O GitHub Actions executa testes estáticos Python (Python 3.12) em oito suítes
independentes para cada PR e push na `main`: configurações/interface,
`admin-api`, `queue-api`, `ai-worker`, AGI, scripts do Asterisk,
backup e scripts operacionais. Veja [Manual 66](docs/manual-66-ci-e-validacao.md)
para execução local, critérios de revisão e limites da validação.

**CI verde não equivale à homologação de telefonia**: testes de registro SIP,
RTP/SRTP, URA, AMI e isolamento multiempresa exigem ambiente de integração
com Asterisk e clientes SIP reais antes da implantação.

## Interface AXE PABX — padrão visual do Despacho

As cinco telas web seguem o padrão do projeto
[`jeffaxe81/dispatch`](https://github.com/jeffaxe81/dispatch): fundo claro,
cartões brancos, destaque azul-petróleo, menu lateral com ícones e
cabeçalho operacional. O menu pode ser recolhido no desktop e abre
como painel no celular.

- Telefonista: conexão, discador e controles de chamada, com orientação
  inicial antes da conexão. Os atalhos para outras telas abrem em outra
  aba para manter o console WebRTC carregado.
- Painel operacional, campanhas e relatórios: navegação e componentes
  visuais consistentes, com cartões responsivos e tabelas roláveis.
- Administração: seções Ramais, Atendimento, Segurança, Usuários,
  Empresas e Áudios e IA; preserva as permissões dos perfis existentes.

O Docker Compose continua servindo o webphone na porta **8082** e a
administração na porta **8091**. Para proxy reverso ou URLs diferentes,
os parâmetros `web`, `admin` e `api` permitem configurar os atalhos.
Não são usados para autenticar ou transportar senhas/chaves.
Configuração, teste manual e limitações no
[manual 67](docs/manual-67-interface-despacho.md).

Os arquivos comuns ficam em `ui/`. Após alterar o CSS ou a navegação:

```bash
python3 scripts/sync_ui.py
python3 scripts/sync_ui.py --check
node --test tests/ui_navigation.test.cjs
```

O sincronizador embute o conteúdo nas páginas HTML para manter os
servidores atuais e a PWA sem novas rotas ou dependências de frontend.

## Segurança dos DIDs de entrada

O contexto `from-tdm-gateway` só encaminha chamadas externas quando
o DID identifica explicitamente um tenant: regras estáticas de t1/t2
ou `tenant-did/<DID>` no AstDB, registrado pelo wizard. DIDs
desconhecidos são **rejeitados**, e não encaminhados a t1.
Consultar o [Manual 68](docs/manual-68-did-sem-tenant.md) antes
de uma atualização: números que dependiam do fallback anterior
precisam ser cadastrados, e o isolamento deve ser homologado com
chamadas SIP reais.

## Diagnóstico do Asterisk antes da homologação SIP

O script `scripts/sip_preflight.py` consulta, em **modo somente leitura**,
os transportes TLS/WSS, ramais PJSIP, dialplan de DID e canais ativos.
Executa no contêiner local ou no Asterisk instalado no Linux, sem
fazer chamadas e sem alterar arquivos ou banco.

```bash
python3 scripts/sip_preflight.py --runtime docker --container pabx-mvp
```

A saída é um relatório JSON e a documentação está no
[Manual 69](docs/manual-69-diagnostico-sip.md).
Este diagnóstico **não** homologa registro SIP, áudio, RTP/SRTP,
URA, contingência nem isolamento entre tenants durante chamadas reais.

## Checagem segura da autenticação AMI

O verificador pós-implantação agora solicita o segredo AMI com
digitação oculta e processa respostas TCP fragmentadas, evitando
falsos resultados e recusando campos inválidos. Executa somente
uma ação de login, sem mudanças na configuração do Asterisk.
Consulte o [Manual 70](docs/manual-70-verificador-ami.md).

```bash
python3 scripts/verify_deployment.py
```

**Importante:** login AMI aceito não substitui os testes de chamada
real, isolamento entre tenants nem verificação de qualidade RTP.

## Wizard multiempresa — validação defensiva

Na criação e remoção de empresas, o `admin-api` recusa payloads JSON de
formato inesperado, IDs inválidos, DIDs com letras e nomes de exibição
com caracteres de controle. O cadastro deve permanecer íntegro antes
de qualquer gravação em arquivos ou mapeamento AstDB.

Consultar o [Manual 71](docs/manual-71-validacao-wizard-tenants.md) para
os testes e as limitações desta proteção.

## Credenciais SIP do wizard de empresas

A criação de tenant `t3+` gera duas senhas SIP fortes e independentes,
uma para cada telefonista WebRTC. O painel as mostra ao administrador
no resultado inicial, com opção de ocultar; elas não aparecem na
listagem de empresas. Os campos exibidos no wizard usam `textContent`
para evitar interpretação de HTML de dados de cadastro.

Veja o [Manual 72](docs/manual-72-segredos-sip-wizard.md). Os exemplos
estáticos t1/t2 continuam exigindo troca de segredos antes de produção.

## Homologação operacional e critérios de GO

O CI do GitHub não substitui a validação de ligações em laboratório.
Para registrar **13 cenários obrigatórios** (SIP/TLS, RTP/SRTP, DID,
isolamento, fila/URA, gravações, restauração e contingência) e
calcular o percentual de evidências aprovadas, use:

```bash
python3 scripts/homologation_gate.py --file /caminho/privado/evidencias.json
```

Copie o [modelo de evidências](docs/modelo-homologacao-pabx.json) para
um diretório privado e informe o SHA completo do commit testado.
A ferramenta só declara **apto para revisão de GO** quando todos
os cenários estiverem marcados como aprovados com referência de
evidência; ela não faz chamadas nem verifica o conteúdo das provas.
Veja [Manual 73](docs/manual-73-gates-homologacao.md).

## PINs de caixa postal das telefonistas

O wizard de novos tenants gera PINs distintos e aleatórios de oito
dígitos para as caixas postais, além de senhas SIP fortes. Os PINs
aparecem somente no resultado da criação para o administrador.
Caixas existentes (inclusive t1/t2) não são alteradas automaticamente.
Consulte o [Manual 74](docs/manual-74-voicemail-pins-seguros.md).

## Conflitos de DID no wizard multiempresa

O cadastro de uma nova empresa verifica também os DIDs já definidos
diretamente no contexto `from-tdm-gateway` do `extensions.conf`.
Se um DID já possuir rota fixa, a criação é recusada antes de gerar
arquivos ou registrar informações no AstDB. Em caso de dialplan
indisponível, a validação falha de forma segura.

Ver o [Manual 75](docs/manual-75-did-estatico-colisao.md). A conferência
de faixas de DIDs, regras da operadora e chamadas reais ainda depende
da homologação.

## Segurança da interface administrativa

As listas de ramais, números bloqueados, destinos VIP e usuários
renderizam dados da API como **texto**, sem interpolação de HTML.
Os testes de navegador incluem entradas adversariais que não podem
executar código. Veja o [Manual 76](docs/manual-76-xss-tabelas-admin.md).

## Segurança das tabelas administrativas

As tabelas de ramais, números bloqueados, clientes VIP e usuários
agora criam elementos DOM com `textContent`, evitando interpretar
valores vindos das APIs como HTML. Um teste real de navegador injeta
um payload HTML simulado e verifica que ele não é executado, sem
alterar dados operacionais ou iniciar chamadas.
Veja o [Manual 76](docs/manual-76-xss-tabelas-admin.md).

## Verificador de implantação: configuração obrigatória

`scripts/verify_deployment.py` agora reprova a checagem de segredos
caso `docker-compose.yml`, `asterisk/manager.conf` ou
`asterisk/pjsip.conf` estejam ausentes, vazios ou ilegíveis,
em vez de ignorá-los. Consulte o [Manual 77](docs/manual-77-arquivos-segredos-obrigatorios.md).

## Segurança na listagem de gravações

O índice de gravações da API ignora links simbólicos; a leitura
individual também rejeita aliases. A mudança inclui regressões
automatizadas, sem alterar o fluxo de chamadas SIP.
Consulte o [Manual 78](docs/manual-78-indice-gravacoes-seguro.md).

## Cadastro de ramais — validação de dados e senha SIP

O painel administrativo rejeita payloads JSON de tipos inválidos e
campos que poderiam introduzir diretivas em PJSIP ou voicemail.
Novos ramais sem senha recebem um segredo SIP aleatório forte, mostrado
uma única vez ao administrador para provisionamento e ocultado ao sair.
O formulário não mostra a senha durante a digitação e o cadastro de
ramais antigos preserva seus segredos existentes até uma rotação
controlada. Veja o [Manual 79](docs/manual-79-ramais-validacao-segredos.md).

## Acesso autenticado a gravações por tenant

A listagem e a reprodução de gravações ficam bloqueadas sem um token
Bearer válido, escopo de tenant e vínculo explícito do áudio à empresa.
O Webphone carrega os áudios via requisições autenticadas e URLs Blob,
sem divulgar tokens em parâmetros de URL. A política é armazenada em
volume privado e o acesso fica desativado quando está ausente.
Essa etapa não substitui SSO, TLS no proxy e homologação operacional.
Ver o [Manual 80](docs/manual-80-acesso-gravacoes-tenant.md).

## PIN de voicemail dos novos ramais

A criação de um ramal pelo painel administrativo gera agora um PIN
aleatório de oito dígitos para seu correio de voz, além da senha SIP.
Os dois segredos são apresentados somente no resultado inicial do
cadastro. Ramais antigos sem PIN persistido mantêm o comportamento
anterior e **precisam de rotação administrada**, sem troca automática.
Confira o [Manual 81](docs/manual-81-pins-voicemail-ramais.md).

## Ramais provisionados em tenants dinâmicos (t3+)

O painel agora aceita ramais nos tenants criados pelo wizard, consultando
um catálogo de IDs provisionados em vez de aceitar livremente o ID
informado na requisição. O Asterisk recebe os arquivos de dialplan,
hints e voicemail de cada tenant, inclusive arquivos inicialmente
vazios durante o cadastro. O seletor mostra os tenants habilitados
para administrador e supervisor sem expor DIDs ao supervisor.

Consulte o [Manual 82](docs/manual-82-ramais-tenants-dinamicos.md).

## Importação em lote de gravações por tenant

O utilitário `queue-api/recording_catalog.py` importa lotes de
áudios previamente conferidos por um operador para o catálogo
privado de acesso a gravações. Por padrão somente simula mudanças;
`--apply` exige referências explícitas de evidência, recusa
classificações conflitantes entre empresas e persiste os dados com
lock e troca atômica, sem modificar credenciais existentes.
Veja o [Manual 83](docs/manual-83-catalogo-gravacoes.md).

## Gerência de credenciais de gravações

O utilitário local `queue-api/recording_credentials.py` emite
credenciais temporárias por tenant e papel e permite revogá-las
por hash sem guardar os tokens em texto claro no catálogo. A
política permanece privada no servidor, com lock e escrita atômica.
A etapa ainda não integra o login do administrador ao Webphone.
Consulte o [Manual 84](docs/manual-84-credenciais-gravacoes.md).

## Persistência segura do cadastro de ramais

O `admin-api` agora salva `extensions_store.json` usando temporário
privado e substituição atômica, além de serializar operações CRUD
simultâneas dentro do mesmo processo. Arquivos JSON inválidos e
symlinks são recusados para evitar perda de dados ou gravações
inseguras. Consulte o [Manual 85](docs/manual-85-cadastro-ramais-atomico.md).

## Limites de requisições JSON do painel

O `admin-api` limita corpos JSON a 64 KiB, recusa cabeçalhos HTTP
ambíguos e documentos que não sejam objetos JSON. Uma requisição
inválida provoca fechamento da conexão para não reaproveitar bytes
residuais. Consulte o [Manual 86](docs/manual-86-limites-json-admin.md).

## Atualização segura das configurações do Asterisk

A recarga dos arquivos dinâmicos do PABX agora utiliza publicação por
temporários e restauração dos arquivos anteriores quando a etapa AMI
ou a publicação falha. O Docker Compose passa a compartilhar o diretório
`asterisk/generated/` (somente leitura no Asterisk), evitando o
problema de `os.replace` com bind mounts individuais.

**Instalações existentes precisam de migração prévia dos arquivos
dinâmicos e recriação do container Asterisk em janela aprovada.**
A mudança não substitui backup nem garante rollback de AstDB e dados
do painel. Consulte o [Manual 87](docs/manual-87-publicacao-asterisk-rollback.md).

## Pré-check da migração de configurações Asterisk

O utilitário `scripts/check_generated_migration.py` verifica, sem
modificar o servidor, se a pasta `asterisk/generated/` possui os
arquivos dinâmicos e includes esperados. Ele aceita o catálogo de
empresas para checar `t3+` e a opção `--compare-legacy` para
conferir cópias antigas antes da migração. Consulte o
[Manual 88](docs/manual-88-precheck-gerados-asterisk.md).

## Conciliação de gravações com CDR do Asterisk

Os dialplans agora registram `CDR(accountcode)` com o ID do tenant
nos fluxos estáticos e nas configurações dinâmicas. O utilitário
`queue-api/recording_cdr_candidates.py` cruza eventos CDR de fonte
confiável com gravações locais e **somente sugere** um manifesto se
accountcode, contexto, ramal, horário, origem e destino concordarem.
Conflitos e dados ambíguos são rejeitados; nenhuma gravação é
liberada automaticamente. Veja o [Manual 89](docs/manual-89-conciliacao-cdr-gravacoes.md).

## Respostas completas no cliente AMI administrativo

O cliente AMI agora reconstrói respostas TCP fragmentadas, exige
`ActionID` correspondente e ignora eventos assíncronos antes da
resposta. Limites de tamanho e timeout impedem espera indefinida e
respostas incompletas. Os testes usam socket simulado; o resultado
de reload ainda deve ser verificado no Asterisk real.
Veja o [Manual 90](docs/manual-90-ami-tcp-framing.md).

## Consultas AMI de VIPs, bloqueios e transbordo

As consultas de listas AstDB usam `ActionID` e só retornam após
`DBGetTreeComplete`, evitando respostas parciais e períodos de espera
fixos. Também filtram as entradas pela família do tenant e preservam
o timeout do socket. Veja o [Manual 91](docs/manual-91-ami-dbgettree-eventos.md).

## Verificação de comandos Asterisk via AMI

Além de reconhecer respostas completas e `ActionID`, o cliente AMI
verifica mensagens explícitas de erro no resultado textual dos comandos
`pjsip reload`, `dialplan reload`, `voicemail reload`, `queue reload all`
e `parking reload`. Uma rejeição interrompe a sequência e aciona a
tentativa de restauração da configuração anterior (Manual 87).
A confirmação do funcionamento real ainda depende da homologação.
Veja o [Manual 92](docs/manual-92-validacao-semantic-reload-ami.md).

## Confirmação obrigatória de escrita AstDB

As operações AMI que registram ou excluem mapeamentos de ramais e
associações DID/tenant só são consideradas concluídas quando recebem
`Response: Success`. Erros são tratados explicitamente, permitindo
que os fluxos de atualização acionem a compensação possível.
Consulte o [Manual 93](docs/manual-93-confirmacao-astdb-ami.md).

## Criação recuperável de novos tenants

O wizard só retorna HTTP 201 após gerar os arquivos do tenant,
confirmar o DID e a recarga no AMI e persistir o cadastro JSON.
Uma falha remove os arquivos novos e tenta compensar o DID em nova
sessão AMI. Se não for possível confirmar a compensação, a API
sinaliza `rollback_incomplete=true` para reconciliação manual.
Veja o [Manual 94](docs/manual-94-tenant-create-compensation.md).

## Remoção recuperável de empresas

O wizard agora guarda snapshots dos arquivos Asterisk e do cadastro
de ramais ao excluir tenants. Se ocorrer erro no AMI ou no salvamento,
a operação tenta restaurar arquivos, ramais e associação DID,
retornando erro quando a exclusão não for confirmada. Consulte o
[Manual 95](docs/manual-95-remocao-tenant-compensavel.md).

## Auditoria do Asterisk em laboratório

O comando `python3 scripts/asterisk_lab_audit.py --runtime docker`
consulta o Asterisk **em execução** via CLI somente leitura.
Verifica presença dos transportes TLS/WSS, contexto SIP dos ramais
por tenant, dialplan de entrada e (com catálogo privado fornecido)
os mapeamentos DID do AstDB, sem divulgar valores no relatório.
O resultado não comprova chamadas, registro, mídia RTP/SRTP ou GO.
Veja o [Manual 96](docs/manual-96-auditoria-runtime-asterisk.md).

## Reconhecimento do contexto PJSIP no Asterisk

A auditoria de runtime reconhece agora a saída realista de
`pjsip show endpoint`, inclusive a opção `context : tN-internal`
com variações de espaços e letras. Regressões impedem confundir
contextos cruzados ou nomes parecidos. Veja o
[Manual 97](docs/manual-97-pjsip-cli-compat.md).

## Recuperação do cadastro de tenants após falha de escrita

A criação e remoção de empresas agora preservam um snapshot do catálogo
`tenants.json`. Se a gravação falhar mesmo depois de substituir o
arquivo, tentam restaurar os bytes e permissões anteriores e sinalizam
`rollback_incomplete` caso a compensação não seja confirmada.
Veja o [Manual 98](docs/manual-98-tenant-registry-compensation.md).

## Programa antecipado de quatro meses — 16 semanas

O [plano de 16 semanas](docs/plano-16-semanas-pabx.json) organiza
homologação SIP real, segurança multiempresa, restauração, carga e
revisão operacional com critérios de aceite por marco. Consulte o
[Manual 99](docs/manual-99-plano-16-semanas-pabx.md).
O progresso pode ser calculado por
`python3 scripts/program_progress.py --format markdown`.
O script não testa chamadas nem concede autorização de GO.

## Evidências de release com SHA comum

O `scripts/release_evidence.py` cruza a auditoria CLI do Asterisk e
os 13 testes declarados de homologação com o SHA completo do release.
Relatórios divergentes ou incompletos bloqueiam a revisão. A saída
inclui hashes dos arquivos de evidências, mas não autentica as provas,
não executa chamadas e **não autoriza GO**.
Veja o [Manual 100](docs/manual-100-release-evidence.md).

101. [Laboratório real de registro SIP/TLS](docs/manual-101-laboratorio-sip-real.md)
102. [Chamadas internas reais com SRTP](docs/manual-102-chamadas-srtp-reais.md)
103. [Webphone real com WSS e DTLS-SRTP](docs/manual-103-webrtc-real.md)
105. [Trilha CEL e CDR correlacionado no aceite de DIDs](docs/manual-105-cel-dids.md)
106. [Auditoria estática de isolamento multiempresa — marco 8 parcial](docs/manual-106-isolamento-estatico.md)
107. [Gravações: isolamento ACL por tenant](docs/manual-107-gravacoes-isolamento-acl.md)
108. [Roteamento seguro de filas por empresa](docs/manual-108-filas-por-tenant.md)
109. [Negativas SIP reais entre empresas](docs/manual-109-negativas-sip-entre-empresas.md)
110. [Catálogo ACL de gravações com leitura atômica](docs/manual-110-catalogo-acl-atomico.md)
