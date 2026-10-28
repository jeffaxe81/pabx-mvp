# Manual 127 — Primeira evidência de AMI em Asterisk real

## Escopo comprovável

Adicionar um teste opcional `--ami` ao laboratório descartável do Asterisk
22.11. O perfil de laboratório reescreve `manager.conf` apenas na área
temporária privada com credencial aleatória e bind **127.0.0.1:5038**.
Os ramais reais, a configuração versionada de produção e o tronco
externo não são modificados.

A ação `Originate` usa `Local/start@axe-ami-lab/n` e associa
`ActionID` aleatório a `ChannelId` explícito. A biblioteca
`queue-api/ami_client.py` efetua login e a função de
`outbound_correlation.py` verifica `OriginateResponse.Uniqueid`.
O relatório publicado só contém booleanos, contagens e metadados
sanitizados do runtime; **nenhum evento AMI bruto ou credencial**.

## Como executar em checkout isolado com Docker

```bash
python3 -m lab.asterisk_lab --ami --report lab-results/ami-originate.json
```

Há job próprio no workflow `asterisk-lab.yml`. Os critérios de aceite
exigem login, ACK da ação, evento único, identidade `ActionID/Uniqueid`,
resultado de originação e dois controles negativos de identidade,
além das verificações de configuração e limpeza do container.

## O que não está homologado

A prova `Local/` **não** representa uma chamada real de campanha nem
callback, nem atesta `DialEnd` de duas pernas. O campo
`live_ami_dialend_correlated` permanece explicitamente **false**.
O envio assíncrono de `Originate` não basta para comprovar atendimento.
Restam a origem em PJSIP autenticado, os dois tipos de chamadas
e os resultados atendido/não atendido, com CDR e vínculo bidirecional
de `DialBegin`, `DialEnd` e `Linkedid`.

Esta entrega é fase inicial da issue #79. Nenhuma homologação ou GO
operacional automático é autorizado.
