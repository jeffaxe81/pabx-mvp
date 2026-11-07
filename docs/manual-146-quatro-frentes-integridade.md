# Manual 146 — Quatro frentes: integridade de chamada, callback, voicemail e SLA

## Objetivo

Reforçar o aceite de laboratório do AXE PABX em quatro frentes sem
confundir testes de contrato/robustez com homologação funcional de
produção. Este manual acompanha a PR #378.

### 1. WebRTC — CDRs independentes das seis chamadas reais

O laboratório Chromium continua realizando três tenants (`t1/t2/t3`)
em duas direções (`1010 → 1011` e `1011 → 1010`).
A prova CDR exige agora **um único registro íntegro por chamada**,
com origens PJSIP `recepcao`/`recepcao-2`, destino, contexto,
disposição ANSWERED, duração válida e `uniqueid` exclusivo entre
todas as chamadas. CDR duplicado, reciclado ou malformado bloqueia o
aceite do navegador. Nenhum identificador é publicado no relatório.

Implementação: `lab/webrtc_checks.py`; regressões em
`scripts/tests/test_webrtc_checks.py`.

**Limite:** não testa operador atendendo por `Queue` nem a gravação
automática da fila WebRTC até o acesso HTTP.

### 2. Callbacks — isolamento de tentativas AXE

`matches_dial_event` recusa um evento AMI `DialEnd` que declare
um canal da tentativa corrente junto com outro canal
`axe-<attempt_id>` diferente. Também recusa IDs com tipos, tamanhos
ou caracteres inesperados. A segunda perna SIP com Uniqueid
normal continua aceita; uma dica `AttemptID` nunca substitui
identidade de canal contraditória.

Implementação: `queue-api/outbound_correlation.py`; testes em
`queue-api/tests/test_callback_mixed_axe_ids.py`.

**Limite:** não demonstra callback atendido e concluído na telefonia
real com OriginateResponse e DialEnd da mesma tentativa.

### 3. Voicemail — limite de tentativas

O preflight de `voicemail.conf` no Asterisk descartável exige
exatamente uma configuração `maxlogins` efetiva em `[general]`,
com valor entre 1 e 3. Ausência, valor excessivo, duplicação,
outro contexto ou texto inválido impedem a inicialização do
laboratório. Não imprime nem grava valores de PIN em evidências.

Implementação: `lab/voicemail_pin_checks.py` e
`lab/asterisk_lab.py`; testes em
`scripts/tests/test_voicemail_maxlogins.py`.

**Limite:** isso valida configuração e **não** comprova autenticação
real com PIN correto/incorreto, lockout e leitura negada entre tenants.

### 4. SLA — consistência sob simultaneidade

A trilha de eventos `AgentConnect`/`QueueCallerAbandon`, o
conjunto de `Uniqueid` já processados, o fechamento à meia-noite
e os snapshots de supervisão passam a usar o mesmo bloqueio
reentrante (RLock) por tracker. Isso impede que consultas HTTP e
eventos AMI simultâneos provoquem duplicação/contagens parciais.
Testes com múltiplas threads cobrem reentrega do mesmo ID, isolamento
entre `fila-t1` e `fila-t10` e persistência uma única vez
na virada do dia.

Implementação: `queue-api/queue_sla.py`; regressões em
`queue-api/tests/test_sla_parallel_events.py`.

**Limite:** não substitui homologação de SLA baseada nos eventos
AMI reais de atendimento de fila por operador.

## Gate de integração

Exigir aprovação integral, **sobre o mesmo HEAD**, dos workflows de
validação estática, Asterisk/Docker real e pacote RC. Em caso de
falha, corrigir e executar novamente; nunca declarar GO.

Os critérios formais `recordings_real`, `voicemail_messages`,
`callback_outcome` e `sla_report` permanecem pendentes. O
progresso ponderado técnico continua **51,3%**, o formal **7/16
(43,8%)**, até que provas fim a fim sejam aceitas.
