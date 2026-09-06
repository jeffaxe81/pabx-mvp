# Manual 06 — Telefonista web (WebRTC + presença/BLF)

## O que é
Interface no navegador (`webphone/index.html`) que permite atender e
fazer chamadas sem instalar softphone nem telefone físico, incluindo
ver em tempo real quais colegas estão livres, tocando ou em chamada, e
transferir com um clique.

## Como configurar
1. `asterisk/http.conf` habilita o servidor WebSocket seguro (WSS) do
   Asterisk, porta `8089`, usando o mesmo certificado de
   `asterisk/certs/`
2. `asterisk/pjsip.conf` define o template `endpoint-webrtc`
   (`webrtc=yes`, `media_encryption=dtls`, `ice_support=yes`) e o
   ramal `t1-recepcao` (número `1000`) que o usa
3. `asterisk/extensions.conf` roteia o número `1000` pro ramal web, e
   define os `hint`s em `[t1-hints]`/`[t2-hints]` que alimentam a
   presença (BLF)
4. `webphone/index.html` conecta nesse WSS via **JsSIP**; o array
   `COLLEAGUES` no início do `<script>` define quais ramais aparecem
   no painel de presença — precisa bater com os `hint`s configurados

## Como testar manualmente
1. `docker compose up -d`
2. Acesse `http://<ip-do-servidor>:8082`
3. **Primeiro**, abra `https://<ip-do-servidor>:8089` direto no
   navegador e aceite o aviso de certificado inválido (necessário por
   ser self-signed — sem isso o WebSocket é bloqueado silenciosamente)
4. Na interface, conecte com servidor `wss://<ip-do-servidor>:8089/ws`,
   ramal `t1-recepcao` e a senha definida em `pjsip.conf`
5. Confirme que o painel "Colegas" aparece e mostra os ramais
   cadastrados em `COLLEAGUES`
6. De outro softphone (ramal `t1-1001`), disque `1000` — a chamada
   deve tocar na interface web, com botões Atender/Recusar
7. Atenda e confirme áudio nos dois sentidos
8. Ligue de um terceiro ramal para o `t1-1001` enquanto ele está livre
   — a bolinha dele na interface web deve mudar pra "Tocando" e depois
   "Em chamada"
9. Durante uma chamada ativa na interface web, clique num colega
   marcado como "Livre" — deve transferir a chamada na hora

## Teste automatizado
`tests/test_webphone_html.py` — garante que os IDs usados pelo
JavaScript continuam no HTML e que o array `COLLEAGUES` não foi
removido por engano
`tests/test_pjsip_conf.py::test_web_endpoint_uses_webrtc_and_wss`
`tests/test_pjsip_conf.py::test_subscribe_context_points_to_existing_hint_context`

## Limitações conhecidas
- Certificado self-signed exige o passo manual de aceitar o aviso do
  navegador (passo 3 acima); em produção, usar certificado válido
  remove essa fricção
- Parsing do XML de presença (`dialog-info`) é feito com regex simples,
  não um parser XML completo — funciona para o formato padrão do
  Asterisk, mas pode precisar de ajuste se algum telefone físico
  específico mandar um formato ligeiramente diferente
- Uma segunda chamada simultânea é recusada automaticamente (sem
  suporte a múltiplas linhas ainda — backlog #4 no prompt master)
- Só existe transferência **cega** (sem consulta antes) — backlog #1
