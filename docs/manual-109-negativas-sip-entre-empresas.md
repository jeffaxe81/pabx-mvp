# Manual 109 — Negativas SIP reais entre empresas

## Escopo desta entrega
O laboratório descartável Asterisk 22 (Docker, loopback, TLS e SRTP)
executa tentativas **reais** de t1 para o endpoint de t2, de t2 para t1
e de t3 para t2. Os ramais são autenticados e o endpoint estrangeiro
permanece registrado e observado. O teste só aprova quando:

- O INVITE inicial passa pelo desafio de autenticação SIP, e a chamada
  autenticada recebe rejeição definitiva de rota inexistente (404 ou 484).
- Um observador independente no telefone estrangeiro permanece íntegro
  e registra **zero INVITEs**.
- Não restam canais PJSIP de chamadas ao final.
- Se o Asterisk gerar CDR novo para a rejeição, ele precisa pertencer
  ao contexto/ramal chamador, não ter canal de destino nem ANSWERED,
  e possuir duração faturável zero.
- Se o PJSIP rejeitar o INVITE **antes de executar o dialplan**,
  o Asterisk pode legitimamente não gerar CDR novo. O teste exige
  então os seis CDRs de chamadas positivas anteriores ainda presentes
  e intactos no mesmo laboratório; zero novos CDRs, combinado à
  rejeição SIP autenticada, observador sem INVITE e zero canais ativos,
  é evidência do não encaminhamento. Um CDR novo malformado ou entregue
  não é aceito.
- Todos os checks do relatório são booleanos `true`, têm nomes
  previstos e pertencem ao **mesmo commit** da execução.

## Execução
```bash
python3 -m pytest -q scripts/tests/test_sip_tenant_isolation.py
python3 -m lab.asterisk_lab --calls --isolation --report lab-results/tenant-isolation.json
```

A segunda linha precisa de Docker e instala cliente SIP/SRTP de
laboratório. A CI possui o job dedicado
`Asterisk | tentativa SIP cruzada entre empresas`.
O modo `--isolation` exige `--calls`, prepara três empresas e
nunca altera o checkout nem a configuração persistente do cliente.

## Registro de evidências
O JSON sanitizado contém `source_commit`, checks, resultado e
`live_sip_extension_isolation_tested`. **Não contém** segredos SIP,
endereços privados de origem externa ou dados de áudio.

## Limites
Mesmo com estes checks aprovados, o indicador de **isolamento completo**
`live_tenant_isolation_tested` continua `false`. São pendentes
tentativas HTTP/API, dialplan/filas e voicemail em runtime, segregação
de arquivos de gravação, AstDB, RBAC e infraestrutura real de destino.
O marco 8 segue aberto e o GO de produção não está autorizado.
