# Manual 01 — Core: ramais e chamadas internas

## O que é
A base do PABX: ramais SIP registrados no Asterisk, chamadas entre
eles, teste de eco e correio de voz.

## Como configurar
Ramais vivem em `asterisk/pjsip.conf`, um bloco `endpoint` + `auth` +
`aor` por ramal (mesmo nome nos três). O roteamento de quem liga pra
quem vive em `asterisk/extensions.conf`, dentro do contexto do tenant
(ex: `[t1-internal]`).

Para adicionar um ramal novo no tenant 1:
1. Copie um bloco de ramal existente em `pjsip.conf` (ex: `t1-1002`),
   troque o nome e a senha
2. Adicione `exten => <numero>,1,Dial(PJSIP/<nome-do-endpoint>,20)` em
   `[t1-internal]` no `extensions.conf`
3. Se quiser esse ramal visível no BLF da telefonista web, adicione
   também `exten => <numero>,hint,PJSIP/<nome-do-endpoint>` em
   `[t1-hints]` (ver manual 06)

## Como testar manualmente
1. `docker compose up -d`
2. Registre dois softphones (Zoiper/Linphone) com usuário/senha de
   dois ramais do mesmo tenant, servidor `<ip>:5060` (UDP, sem TLS)
3. De um ramal, disque o número do outro — deve tocar
4. Disque `600` — teste de eco, confirma que o áudio (RTP) está
   passando
5. Não atenda uma chamada de propósito — deve cair na caixa de voz;
   disque `*97` no ramal chamado para ouvir a mensagem (senha padrão
   `1234`, definida em `voicemail.conf`)

## Teste automatizado
`tests/test_pjsip_conf.py::test_every_endpoint_has_matching_auth_and_aor`
`tests/test_extensions_conf.py::test_tenants_do_not_share_extension_numbers_in_same_context`

## Limitações conhecidas
- Sem fila de atendimento (backlog #2 no prompt master)
- Sem gravação de chamadas (backlog #3)
- Sem multi-chamada / segunda linha (backlog #4)
