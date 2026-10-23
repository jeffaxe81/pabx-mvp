# Manual 92 — Verificação semântica dos comandos de reload AMI

## Problema

O Asterisk Manager Interface (AMI) pode retornar `Response: Follows`
para a ação `Command`, mesmo quando o texto produzido pelo CLI é
`No such command` ou indica falha de recarga. Antes, o AXE PABX
avaliava somente a resposta de transporte e poderia registrar uma
recarga como concluída, ainda que o comando não fosse reconhecido.

## Alteração

O cliente `admin-api/ami_client.py` passa a coletar, de maneira
limitada, a saída textual de `Response: Follows` e verificá-la
antes de aceitar cada uma das cinco recargas:

- `pjsip reload`
- `dialplan reload`
- `voicemail reload`
- `queue reload all`
- `parking reload`

Padrões explícitos como `No such command`, `Unknown command`,
`Failed to reload` e `Unable to reload` bloqueiam imediatamente a
sequência e propagam erro ao publicador de configurações, que tenta
restaurar os arquivos anteriores conforme o Manual 87.

A política não trata qualquer palavra `error` como fracasso:
relatórios como `0 errors` não devem provocar falso positivo.
Saídas e mensagens AMI completas não são devolvidas ao painel;
somente os estados de execução ou um erro genérico com o componente.

## Verificações automatizadas

```bash
(cd admin-api && python3 -m pytest -q \
  tests/test_ami_reload_semantics.py \
  tests/test_ami_client_framing.py \
  tests/test_conf_publisher.py)
```

Os testes simulam rejeição de comando, falha no segundo componente,
saída fragmentada em pacotes TCP, excesso do limite de buffer e
desvinculação entre o texto privado do AMI e a resposta do painel.

## Homologação operacional

Executar em ambiente isolado com Asterisk compatível, registrar
antes/depois de `pjsip show endpoints`, `dialplan show` e
`voicemail show users`, validar o resultado real dos comandos e
forçar uma falha controlada de recarga para verificar a compensação.

## Limitações

Esta verificação **detecta alguns erros explícitos**, mas não prova
que todas as alterações foram aceitas. Mensagens de falha que não
correspondam aos padrões reconhecidos, alterações parcialmente
aplicadas e problemas após um comando `Response: Success` podem não
ser detectados. A restauração dos arquivos não reverte automaticamente
ações AstDB/AMI já realizadas nem garante que o runtime foi restaurado.

Não houve conexão com servidor real nem chamada SIP/RTP nesta PR.
