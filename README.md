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

423 testes estáticos no total, em 5 suítes (`tests/`, `queue-api/tests/`,
`admin-api/tests/`, `asterisk/scripts/tests/`, `backup/tests/`) —
nenhuma delas sobe o Asterisk de verdade. Detalhes em `tests/README.md`.

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
