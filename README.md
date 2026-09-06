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

## Próximos passos

- TLS com certificado válido (não self-signed) em produção
- Fila de atendimento por tenant (`queues.conf`)
- URA (IVR) por tenant
- Painel web para cadastro de ramais/tenants (hoje é tudo manual nos
  arquivos `.conf`)
- Suporte a mais fabricantes no auto-provisionamento
