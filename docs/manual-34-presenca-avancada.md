# Manual 34 — Presença corporativa avançada (item #29)

## O que é
Cada telefonista pode marcar manualmente seu próprio status —
**disponível, ausente, em reunião ou férias** — com uma nota opcional
("volto às 15h"). Esse status sobrepõe visualmente o estado
automático do BLF (livre/tocando/ocupado, manual 06/17) em qualquer
painel que mostre presença.

## Como funciona
- **Autoatendimento**: cada ramal define o próprio status (não tem
  "admin definindo status de outra pessoa" neste MVP) — botão "Minha
  presença" no console da telefonista (`webphone/index.html`)
- O status fica guardado num arquivo simples (`presence.json`),
  persistente — diferente do BLF automático, "estou de férias" não
  deveria sumir sozinho se o `queue-api` reiniciar
- O endpoint `/api/extension-states` (já usado pelo painel
  operacional, manual 17) agora devolve o status manual **junto** com
  o estado automático — a interface prioriza mostrar o manual quando
  existir

## Como usar
1. Conecte no console da telefonista normalmente
2. No painel "Minha presença", escolha um status e (opcional) uma nota
3. Clique "Atualizar presença"
4. Qualquer supervisor olhando o painel operacional (manual 17) vê o
   status manual em vez do automático

Pra voltar a "disponível" (automático), é só selecionar "Disponível"
de novo e atualizar.

## Como consultar/gerenciar pela API
```bash
curl "http://<ip>:8090/api/presence"                     # todos os overrides ativos
curl -X POST "http://<ip>:8090/api/presence/t1-recepcao" \
  -H "Content-Type: application/json" \
  -d '{"status": "ferias", "note": "De volta dia 10"}'
curl -X DELETE "http://<ip>:8090/api/presence/t1-recepcao" # remove o override
```

## Como testar manualmente
1. `docker compose up -d`, conecte a telefonista web
2. Marque "Em reunião" com uma nota, clique atualizar
3. Abra o painel operacional — confirme que aparece "Em reunião — [nota]"
   em vez do estado automático do BLF
4. Volte pra "Disponível" — confirme que o painel volta a mostrar o
   estado automático normal

## Teste automatizado
- `queue-api/tests/test_presence.py` — validação de status (só os 4
  valores aceitos), persistência, sobrescrita, remoção, mesclagem com
  o estado automático (preserva `status_label`, adiciona
  `manual_status`/`manual_note`)
- `queue-api/tests/test_server_routes.py`:
  - `/api/extension-states` de fato mescla a presença manual
  - definir presença valida os dados **antes** de persistir
- `tests/test_webphone_html.py` — botão de presença manda a extensão,
  status e nota certos
- `tests/test_ops_panel.py` — painel operacional prioriza visualmente
  o status manual sobre o automático
- `tests/test_docker_compose.py::test_presence_path_configured`

## Sobre sincronização com calendário (não implementado)
O documento de funcionalidades original também pedia "sincronização
com calendário" (ex: marcar "em reunião" automaticamente com base no
Google Calendar/Outlook). **Isso não foi implementado** — é uma
integração com um provedor externo (Google/Microsoft), na mesma
categoria de decisão dos itens de IA do backlog (#21-24): exige
escolher um provedor, credenciais OAuth, e manutenção de uma
integração externa contínua. O mecanismo de presença manual construído
aqui já está pronto pra receber isso como uma extensão futura (bastaria
um serviço que consulta o calendário e chama `POST /api/presence/...`
automaticamente), mas essa integração em si fica fora do escopo deste
MVP.

## Limitações conhecidas (honestidade técnica)
- **Sem sincronização de calendário** (ver seção acima)
- **Sem expiração automática** — se alguém marcar "férias" e esquecer
  de voltar pra "disponível", o status fica lá indefinidamente; não
  há um campo "até quando" que expire sozinho
- **Sem autenticação própria no endpoint** — qualquer um que alcançar
  a porta do `queue-api` pode mudar a presença de qualquer ramal (a
  extensão vem no corpo da requisição, não é verificada contra quem
  está de fato chamando) — aceitável pra uso em rede interna
  confiável, mesma limitação já documentada em outros endpoints do
  `queue-api`
- **Só 4 estados fixos** — não dá pra criar estados customizados
