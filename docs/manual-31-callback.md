# Manual 31 — Chamada de retorno / callback (item #26)

## O que é
Em vez de esperar na fila, o cliente aperta um dígito na URA e recebe
uma ligação de volta quando um atendente estiver disponível — sem
perder a vez (a fila de callback é FIFO, o pedido mais antigo é
discado primeiro).

## Como funciona
1. Na URA (manual 23), durante o horário comercial, o menu agora tem
   uma **opção 9**: "receber uma ligação de retorno"
2. Ao escolher, o cliente ouve uma confirmação (placeholder de áudio,
   mesmo esquema da URA) e a chamada é encerrada — o número dele
   (`CALLERID(num)`) é registrado automaticamente via um evento
   customizado que o `queue-api` já escuta
3. Alguém (supervisor/telefonista) clica "Discar próximo retorno" na
   interface — o sistema pega o pedido **mais antigo pendente** (FIFO)
   e liga **direto pro número do cliente** através do tronco
4. Quando o cliente atende, a chamada é automaticamente conectada com
   um atendente (contexto `callback-connect`)
5. O resultado (atendeu, ocupado, não atendeu) é registrado
   automaticamente via o mesmo evento `DialEnd` já usado em chamada
   perdida (manual 11) e campanhas (manual 30) — sem resposta, tenta
   de novo até **2 vezes** (menos que campanha, que tenta 3 — um
   cliente esperando retorno não deve ser insistido demais)

## Diferença técnica importante em relação ao click-to-call/campanhas
No click-to-call e nas campanhas, o `Originate` liga **primeiro pro
atendente interno**, e só depois completa pro número externo. No
callback é o **contrário**: o `Originate` disca **direto pro número
externo do cliente** através do tronco (`PJSIP/{numero}@gateway-tdm`
como o próprio "Channel" do Originate), e só quando ele atende é que
o dialplan (`callback-connect`) conecta com um atendente. É a mesma
peça de engenharia (AMI Originate), só que montada na ordem inversa —
faz sentido, porque aqui é o cliente que precisa atender primeiro.

## Segurança
Mesma chave do click-to-call/campanhas (`CLICK_TO_CALL_API_KEY`) —
mesma categoria de risco (originar chamada via AMI direto pro tronco).

## Como usar
1. Configure `CLICK_TO_CALL_API_KEY` (manual 12)
2. Acesse `http://<ip>:8082/campanhas.html?api=http://<ip>:8090`
3. Cole a chave, veja o painel "Retornos de chamada pendentes"
4. Clique "Discar próximo retorno" quando um atendente estiver livre

## Como testar manualmente
1. `docker compose up -d`
2. Ligue de um ramal de teste até a URA (disque `700`)
3. No menu, aperte `9`
4. Confirme que ouve o áudio de confirmação e a chamada desliga
5. Na página de campanhas, confirme que o pedido aparece em
   "Retornos de chamada pendentes"
6. Clique "Discar próximo retorno" — o ramal de teste (que "é" o
   cliente nesse teste) deve tocar de volta
7. Atenda — confirme que conecta com a telefonista
8. Confirme que o status vira "Concluído" depois

## Teste automatizado
- `queue-api/tests/test_callbacks.py` — parsing do pedido, fila FIFO
  (mais antigo primeiro), contagem de tentativas com `MAX_ATTEMPTS=2`
  (menor que campanha), mapeamento de disposição pra status
- `queue-api/tests/test_server_routes.py` — rotas de callback exigem
  a mesma chave de API, marcar "discando" acontece antes do
  `Originate` de verdade
- `tests/test_extensions_conf.py` — a URA oferece a opção 9, o
  contexto de solicitação manda o `UserEvent` com o número certo, o
  contexto de conexão disca pro atendente
- `tests/test_ura_sounds.py` — o placeholder de áudio existe
- `tests/test_campaigns_html.py` — painel de retornos filtra os já
  resolvidos, usa o endpoint certo

## Limitações conhecidas (honestidade técnica)
- **Áudio placeholder** (beep), mesma situação da URA (manual 23) —
  precisa trocar por gravação real antes de produção
- **Um atendente fixo** no `callback-connect` (`t1-recepcao`) — não
  escolhe dinamicamente qual telefonista está livre; pra múltiplas
  telefonistas de verdade, o ideal seria rotear pra fila em vez de um
  ramal fixo (ajuste natural de evolução)
- **Sem limite de posição/tempo estimado** mostrado ao cliente — ele
  só sabe que "vai receber uma ligação", não quando
  - Cliente **precisa atender rápido**: se demorar demais ou passar a
  ligação pra caixa postal, conta como tentativa igual a não atender
- **Sem teste de integração real** do fluxo Originate direto pro
  tronco → callback-connect → Dial do atendente — mesma situação já
  documentada pro resto das integrações AMI do projeto
