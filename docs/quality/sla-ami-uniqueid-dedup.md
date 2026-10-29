# Marco 9 — Deduplicação de eventos AMI no SLA

O AMI pode reenviar eventos após reconexões. Se `AgentConnect` ou
`QueueCallerAbandon` da mesma chamada aparecerem repetidamente, a
contagem de chamadas oferecidas pode aumentar artificialmente.

Nesta entrega, um `Uniqueid` textual e seguro identifica a chamada
**por fila e por dia**. A primeira ocorrência terminal é contada;
repetições na mesma fila e dia não alteram numerador nem denominador.
As filas `fila-t1` e `fila-t10` permanecem distintas. O conjunto
de identificadores é descartado na virada do dia.

Valores `Uniqueid` presentes, mas malformados, são desconsiderados
sem criar métrica; eventos AMI legados sem esse campo continuam a
ser processados por compatibilidade, mas não podem ser deduplicados.

## Limites

Esta deduplicação usa memória local do processo e não persiste IDs
em reinícios nem coordena múltiplas instâncias da API. Não comprova
cálculo operacional com tráfego real, que ainda exige ensaios
correlacionados por CDR/AMI, URA, espera, transbordo e callbacks.
O marco 9 permanece em andamento e não há autorização de GO.
