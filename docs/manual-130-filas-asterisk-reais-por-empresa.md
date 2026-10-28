# Manual 130 — Prova da fila correta no Asterisk real

## Finalidade

Laboratório descartável e sem chamadas externas, baseado no mesmo Asterisk
22 e clientes PJSIP autenticados via TLS/SRTP usados nas verificações de
ramal e voicemail. A suíte nova exercita a extensão `1000` com um
chamador autenticado de `t1`, `t2` e `t3`.

A prova compara **o mesmo canal**, de forma indivisível:
nome do endpoint PJSIP, contexto `tN-internal`, extensão `1000`,
aplicação `Queue` e nome **exato** da fila `fila-tN`.
Não se usa comparação por prefixo. Sem correspondência íntegra, a
verificação falha.

## Execução

```bash
python3 -m pytest -q scripts/tests/test_queue_tenant_runtime.py
python3 -m lab.asterisk_lab --calls --queues --report lab-results/queue-tenants.json
```

O job `Asterisk | filas por empresa via SIP real` publica somente
booleanos, metadados de laboratório e SHA de checkout. Nem nomes de
clientes, eventos SIP brutos ou credenciais são publicados.

## Estado de homologação

Esta prova cobre **roteamento Queue no próprio Asterisk**. Em conjunto
com a PR #82, há também checagens HTTP com políticas por tenant, mas
essas etapas **não equivalem** a executar a interface HTTP integrada
simultaneamente ao Asterisk, testar PINs/mailboxes cruzados nem segregar
volumes físicos de gravação.

O marco 8 continua `in_progress` até existir evidência de cada domínio;
**não mudar o status para done nem indicar GO operacional** por passar
uma única suíte.
