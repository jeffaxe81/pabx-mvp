# Manual 148 — Atendimento real em fila e SLA AMI/HTTP

## Meta de avanço técnico

Este incremento busca comprovar o critério parcial **sla_report** da
semana 9 com um evento **AgentConnect de origem Asterisk**, causado por
uma chamada **efetivamente atendida pela aplicação Queue**. O indicador
técnico poderá passar de 51,3% para **52,5%**, mediante aprovação
integral de todas as pipelines no mesmo commit. Isso não representa
60% e não autoriza implantação em produção.

## Laboratório isolado

O novo job "Asterisk | Queue atendida e SLA AMI/HTTP reais" executa:

1. Asterisk descartável, configurado a partir do mesmo código versionado
   e com SIP/TLS e SRTP autênticos. Os endpoints t1-1001/1002,
   t2-1001/1002 e t3-1001/1002 usam credenciais geradas para o ensaio.
2. Apenas no staging, acrescenta a linha "member => PJSIP/tN-1002"
   à **fila original** de cada tenant. As extensões produtivas 1000,
   a aplicação Queue, a estratégia de distribuição e monitor-type
   permanecem inalterados.
3. O SIP tN-1001 entra em 1000; o atendente SIP tN-1002 recebe INVITE,
   envia 200 OK e troca áudio SRTP bidirecional com conteúdo autenticado.
4. O AMI é habilitado **só em loopback**, com usuário temporário e ACL
   127.0.0.1. Uma assinatura recebe evento AgentConnect da mesma
   fila tN e inspeciona seu Uniqueid e HoldTime, sem inventar o evento.
5. O CDR precisa ser uma linha **nova**, com origem tN-1001,
   destino 1000, contexto tN-internal, B-leg tN-1002, disposição
   ANSWERED, duração positiva e Uniqueid do evento AMI.
6. A implementação QueueSLATracker de produção agrega três
   atendimentos (t1,t2,t3), com offered=1, within_sla=1 e
   sla_percent=100.0 para cada fila separadamente.
7. A API HTTP **real** publica somente a fila da empresa autenticada:
   o token de t1 não exibe t2/t3, t10 não é prefix-match, query
   tenant= não altera autorização e sem Bearer a resposta é 401.

## Reprodução

python3 -m pytest -q scripts/tests/test_queue_sla_live_lab.py

python3 -m lab.asterisk_lab --calls --queue-sla --report lab-results/queue-sla-real.json

A prova só é válida com o job aprovado na CI, com checks
individuais por tenant; não basta executar validadores unitários.

## Limites

O atendente desta prova é **SIP/TLS com SRTP**, ainda **não** operador
Chromium WebRTC em Queue. Não comprova gravação com reprodução HTTP
proveniente da Queue nem o resultado de callback, autenticação do
voicemail por PIN e isolamento do spool de mensagens.

Se o job reprovar, **sla_report permanece pending** na main e o
progresso técnico permanece em 51,3%. A homologação formal
permanece em 7/16 marcos (43,8%) até que todos os critérios do
respectivo marco estejam satisfeitos. GO=false.
