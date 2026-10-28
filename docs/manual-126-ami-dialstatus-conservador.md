# Manual 126 — Proteção de resultados AMI não reconhecidos

## Risco corrigido

Quando uma tentativa já reservada em campanha ou callback recebia um
`DialEnd` com `Uniqueid` correlacionado, mas `DialStatus` desconhecido,
o processamento HTTP/AMI podia converter o resultado em falha e liberar
a tentativa para rediscagem (se abaixo do limite de tentativas). Isso
não representa evidência verificável de conclusão.

## Política de reconciliação

A interface do servidor só encaminha resultados AMI conhecidos:
`ANSWER`, `BUSY`, `NOANSWER`, `CANCEL` e `CONGESTION`.
Qualquer valor vazio, desconhecido ou não textual é ignorado:
a tentativa fica em `discando` e depende de revisão manual, em vez de
permitir rediscagem por uma interpretação ambígua.

As outras salvaguardas permanecem: o `ChannelId` deve corresponder ao
`Uniqueid` ou `DestUniqueid`, o tenant deve ser confiável, o telefone
deve coincidir e nenhuma conclusão pode cruzar campanhas ou callbacks.
Não se altera a API de cadastro nem o número de tentativas.

## Testes executáveis

```bash
cd queue-api
python3 -m pytest -q tests/test_outbound_dialstatus_guard.py
```

A suíte contém **18 casos**: 14 negativos para valores desconhecidos
ou não textuais em campanhas e callbacks, 2 positivos de atendimento
com canal identificado e 2 negativos para canal divergente.

Os testes locais usam arquivos temporários e eventos AMI sintéticos.
**Não comprovam** que `OriginateResponse.Uniqueid` e `DialEnd`
correspondem ao `ChannelId` no Asterisk real. Essa homologação
continua pendente, conforme Manual 122.

## Critério de entrega

Integrar somente com CI estática e laboratório Asterisk existentes
aprovados no HEAD desta PR. Merge não equivale a deploy nem a GO.
