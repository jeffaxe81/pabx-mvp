# Manual 113 — Prova de rota real para voicemail *97

## Escopo
Laboratório descartável Asterisk 22 em Docker, em loopback, com
três empresas e clientes SIP autenticados via TLS e mídia SRTP.

A suíte `lab/voicemail_checks.py` liga para `*97` de dentro
de `t1-1001`, `t2-1001` e `t3-1001` e verifica, no CLI do Asterisk:
- O módulo de correio de voz realmente carregou e o dialplan
  de cada tenant contém o guard de `PJSIP_ENDPOINT`.
- O ramal de origem foi registrado com autenticação SIP válida.
- O `INVITE` para `*97` obteve resposta 200.
- O mesmo canal PJSIP executou `VoiceMailMain` com argumento exato
  `ramal@tenant`, sem um mailbox de outro tenant no mesmo canal.
- O encerramento por BYE funcionou e os canais foram limpos.

A evidência `lab-results/voicemail.json` informa somente flags
booleanas, nomes fixos de casos e SHA do checkout. Ela não contém
PINs, senha SIP ou áudio, e só é aprovada se todos os checks
exigidos estiverem presentes.

## Execução
```bash
python3 -m pytest -q scripts/tests/test_voicemail_runtime.py
python3 -m lab.asterisk_lab --calls --voicemail --report lab-results/voicemail.json
```

O workflow `.github/workflows/asterisk-lab.yml` contém o job
`Asterisk | caixa postal *97 por empresa (SIP real)`.

## Limites
A prova de roteamento não entra PIN nem lê mensagens e não envia
um identificador de chamada falsificado. Esses casos são etapas
distintas de homologação; este relatório não deve ser anunciado como
penteste completo, revogação de credenciais ou validação do ambiente
de produção. Em especial, os PINs legados 1234 ainda exigem rotação.

Marco 8 permanece aberto (7/16) e o GO operacional permanece
bloqueado mesmo quando este job passar.
