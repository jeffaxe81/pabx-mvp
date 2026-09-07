# Manual 44 — Motivo de pausa do agente (item #44)

## O que é
A telefonista pausa a si mesma na fila (Almoço, Banheiro, Reunião,
Treinamento, ou motivo livre) — enquanto pausada, o Asterisk **para
de rotear chamadas** pra ela, e o painel de supervisão mostra o
motivo exato, não só "indisponível" sem contexto.

Usa a ação nativa `QueuePause` do Asterisk (via AMI, campo `Reason`) —
não é uma funcionalidade construída do zero, é a exposição correta de
um recurso que já existe.

## Como funciona
1. No console da telefonista, painel "Pausa da fila": escolhe um
   motivo, clica "Pausar"
2. O `queue-api` dispara `Action: QueuePause` com `Interface` (o
   ramal), `Paused: true`, e `Reason` (o motivo)
3. O Asterisk emite de volta um evento `QueueMemberPause` — é esse
   evento (não a chamada em si) que atualiza nosso estado interno,
   então o motivo de pausa fica correto mesmo se alguém pausar por
   outro caminho (ex: CLI do Asterisk, outro sistema)
4. O painel operacional mostra "Pausado — Almoço" com **prioridade
   visual máxima** — antes até da presença manual (manual 34), porque
   pausa afeta se a pessoa recebe chamada *agora*, diferente de um
   status como "ausente" que é mais informativo

## Sem `Queue` especificado
Ao pausar, não informamos uma fila específica — isso pausa o agente
em **todas** as filas que ele participa (comportamento padrão do
Asterisk). Faz sentido: "estou almoçando" não deveria significar
"só não me chame na fila de vendas, mas pode me chamar na de
suporte".

## Como testar manualmente
1. `docker compose up -d`, registre a telefonista `t1-recepcao`
2. No console, escolha "Almoço" e clique "Pausar"
3. Ligue pro ramal `1000` (fila) — confirme que **não** toca em
   `t1-recepcao` (só na outra telefonista, se houver)
4. Confira o painel operacional — deve mostrar "Pausado — Almoço"
5. Clique "Voltar da pausa" — confirme que volta a receber chamada
   normalmente

## Teste automatizado
- `queue-api/tests/test_agent_pause.py` (19 testes) — validação
  (motivo obrigatório ao pausar, opcional ao despausar), extração do
  ramal a partir da interface AMI, parsing do evento
  `QueueMemberPause`, rastreamento de estado (múltiplos ramais
  independentes, motivo limpo ao despausar), mesclagem com o estado
  automático
- `queue-api/tests/test_server_routes.py` — validação acontece antes
  da chamada AMI, `/api/extension-states` mescla o motivo de pausa
- `tests/test_webphone_html.py` — botão de pausa envia o motivo,
  despausar não exige motivo nenhum
- `tests/test_ops_panel.py` — motivo de pausa tem prioridade de
  exibição sobre a presença manual

## Limitações conhecidas (honestidade técnica)
- **Sem autenticação verificando "é você mesmo"** — o `queue-api` não
  confirma que quem está chamando `/api/queue/pause` é de fato o
  dono do ramal informado (mesma limitação já aceita nos endpoints de
  presença e pickup deste serviço)
- **Sem lista de motivos fixa no backend** — o `queue-api` aceita
  qualquer string como motivo; os motivos pré-definidos (Almoço,
  Banheiro, etc.) existem só na interface, pra guiar a telefonista,
  não como uma validação de enum no servidor
- **Sem relatório histórico de tempo em pausa por motivo** — o estado
  é só o *atual*; pra métricas tipo "quanto tempo em pausa por dia,
  por motivo", seria preciso persistir o histórico de eventos
  `QueueMemberPause` (natural extensão futura, reaproveitando o
  padrão JSONL já usado em `reports.py`/`survey.py`)
- **Sem teste de integração real** contra o Asterisk de verdade —
  mesma situação já documentada pro resto das integrações AMI do
  projeto
