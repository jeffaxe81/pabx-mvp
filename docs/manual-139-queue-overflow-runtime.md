# Manual 139 — Timeout e transbordo real de filas entre tenants

## Objetivo

Evidenciar, no **Asterisk real e descartável**, o mecanismo já
versionado: quando a fila de idioma `fila-tN-en` não atende dentro
do prazo, a **mesma chamada** transborda para a fila geral
`fila-tN`, sem atravessar a empresa e sem retornar à fila inicial.

A prova cobre `t1`, `t2` e `t3`.

## Como o laboratório executa

1. Apenas no *staging privado*, é acrescentada a extensão `9987`
   ao contexto de cada tenant. Essa entrada define o serviço de
   idioma em inglês e o timeout de **2 segundos**, depois executa
   `Goto(1000,1)`. O bloco original de `1000`,
   `fila-overflow` e `fazer-overflow` não é substituído.
   A entrada é preparada **antes** do snapshot das rotas diretas
   `1010/1011`, de modo que a restauração de seus destinos WebRTC
   não apague a extensão temporária de overflow.
2. Um ramal `tN-1001` registra por SIP/TLS, negocia mídia SRTP e
   liga para `9987`, que entrega a chamada ao fluxo real de fila.
3. Durante a ligação, o laboratório lê `core show channels concise`
   e exige uma linha única e exata da chamada, registrando a
   transição **`fila-tN-en` → `fila-tN`**, com o mesmo ID de canal.
   Confere intervalo mínimo entre as duas observações, impede loops
   de volta ao idioma e rejeita nomes de outros tenants, inclusive
   colisão de prefixos `t1`/`t10`.
4. Ao desligar, exige liberação de canais e CDR de origem/contexto/
   tenant válidos. A conferência CDR captura os `uniqueid` anteriores à
   chamada e só aceita um registro novo **do mesmo canal observado**;
   admite o destino `9987` ou `1000`, pois `Goto(1000,1)` pode atualizar
   a extensão de destino no CDR. O relatório publica apenas booleanos,
   sem identificadores ou números de chamada.

São **33 checks obrigatórios**, incluídos na pipeline já existente
`Asterisk | filas por empresa via SIP real` (`--calls --queues`).
Negativos estáticos cobrem canais duplicados, confusão de empresa,
aplicação diferente de Queue, CDR adulterado e alterações de staging.

## Reprodução

```bash
python3 -m pytest -q scripts/tests/test_queue_overflow_lab.py
python3 -m lab.asterisk_lab --calls --queues \
  --report /tmp/axe-overflow-real.json
python3 scripts/project_progress.py
```

## Avanço técnico e limites

O critério parcial `queue_overflow` da semana 9 só poderá mudar
de **pending** para **verified_lab** mediante todas as pipelines
do mesmo HEAD da PR aprovadas. Isso mede evolução de engenharia,
**não significa aceite formal da semana 9 nem GO de produção**.

A prova não envolve atendimento efetivo por operador WebRTC,
gravação da Queue atendida, callback fim a fim, SLA histórico,
SSO, voicemail PIN ou isolamento de volumes em produção. Estes
itens continuam pendentes.
