# Manual 32 — Pesquisa de satisfação pós-atendimento (item #27)

## O que é
Depois que a telefonista desliga, o cliente ouve automaticamente uma
pergunta rápida: "de 1 a 5, qual sua nota pra este atendimento?" —
sem precisar de nenhuma ação da telefonista. A nota fica associada ao
atendente que participou da chamada, permitindo relatório por equipe.

## O desafio técnico: manter o cliente na linha
Por padrão, quando o atendente desliga uma chamada, o Asterisk também
derruba o lado do cliente — não haveria como rodar uma pesquisa
depois. A solução é a opção **`c`** do `Queue()` e **`g`** do `Dial()`:
em vez de encerrar a chamada quando o lado discado desliga, o
Asterisk **continua executando o dialplan** a partir da próxima
prioridade, com o cliente ainda na linha.

```
exten => 1000,1,Set(CHANNEL(hangup_handler_push)=qualidade-chamada,s,1)
 same => n,Queue(fila-t1,c)              ; "c" = continua depois que o atendente desliga
 same => n,Goto(pesquisa-satisfacao,s,1) ; só roda por causa do "c" acima
```

O mesmo vale pros ramais diretos (`1010`, `1011`, pickup), usando
`Dial(PJSIP/ramal,20,g)` em vez de `Queue(...,c)`.

## Como sabe qual atendente participou
O Asterisk preenche automaticamente a variável `${DIALEDPEERNAME}`
com o canal do último ramal discado (ex: `PJSIP/t1-recepcao-00000003`)
— é isso que vai no evento `UserEvent(SatisfactionSurvey,...,Operator=${DIALEDPEERNAME})`,
e o `queue-api` extrai o nome do atendente daí (mesma lógica já usada
nos relatórios, manual 18).

## Como consultar os resultados
```bash
curl "http://<ip>:8090/api/satisfaction"                    # média geral + distribuição
curl "http://<ip>:8090/api/satisfaction?operator=t1-recepcao" # só de um atendente
curl "http://<ip>:8090/api/satisfaction?group_by=operator"    # média por atendente
```

## Como testar manualmente
1. `docker compose up -d`
2. Ligue até a telefonista (ramal `1000`, `1010` ou via pickup)
3. Fale um pouco, e **a telefonista desliga primeiro**
4. Confirme que o cliente **continua na linha** e ouve o placeholder
   de áudio da pesquisa (5 beeps)
5. Digite uma nota de 1 a 5
6. Confira `/api/satisfaction` — a nota deve aparecer, associada ao
   atendente certo
7. Repita sem digitar nada — confirme que não gera registro (mesma
   lógica de "sem dado não é alarme falso" já usada no monitoramento
   de qualidade, manual 29)

## Teste automatizado
- `queue-api/tests/test_survey.py` — extração de atendente a partir
  do canal, validação de nota (só 1-5 é aceito), persistência em
  JSONL, cálculo de média (nunca `0` quando vazio, sempre `None`),
  distribuição de notas, agrupamento por atendente
- `tests/test_extensions_conf.py`:
  - `test_customer_stays_on_line_after_agent_hangs_up` — confirma que
    **todos** os pontos de chamada da telefonista usam `c`/`g`
  - `test_survey_context_reads_digit_and_sends_user_event_with_operator`
- `tests/test_ura_sounds.py` — placeholder de áudio existe

## Limitações conhecidas (honestidade técnica)
- **Áudio placeholder** (beep), mesma situação da URA e do callback —
  precisa trocar por gravação real dizendo a pergunta de verdade
- **Sem comentário gravado** — o documento de funcionalidades original
  mencionava "comentários gravados ou digitados"; este MVP só captura
  a nota numérica, não um comentário de voz (adicionar isso seria
  gravar após o dígito, reaproveitando o mecanismo de gravação do
  manual 09 — evolução natural, não implementada ainda)
- **`${DIALEDPEERNAME}` pode não vir preenchido** em alguns fluxos
  (ex: se a chamada nunca chegou a discar de fato) — nesse caso a
  nota é salva com `operator: null`, não descartada
- **Sem teste de integração real** do fluxo completo (opção `c`/`g`
  mantendo a chamada viva, `Read()` capturando o dígito) — mesma
  situação já documentada pro resto das integrações que dependem do
  Asterisk de verdade rodando
- **Um único contexto de pesquisa pra todos os pontos de entrada** —
  não há pesquisa diferente por tipo de atendimento (ex: vendas vs.
  suporte)
