# Manual 122 — Correlação OriginateResponse / ChannelId / DialEnd

## O que mudou

A API reserva cada chamada de campanha ou callback com um identificador
`attempt_id` aleatório, gerado antes da ação AMI, e agora grava também
`channel_id = axe-<attempt_id>`. A ação `Originate` envia ambos:

- `ActionID: <attempt_id>`: identifica o pedido AMI.
- `ChannelId: axe-<attempt_id>`: solicita ao Asterisk este identificador
  na **primeira perna do canal originado**. O suporte a `ChannelId`
  depende da versão efetivamente instalada do Asterisk.

Um evento `OriginateResponse` só grava `originate_response` quando
`ActionID` **e** `Uniqueid` correspondem à mesma tentativa persistida;
informações de conta conflitantes são rejeitadas. O resultado da
originação não é confundido com atendimento: `Success` significa
retorno do processo AMI, não uma chamada concluída.

Na reconciliação de `DialEnd`, números telefônicos iguais não
identificam a tentativa. O evento precisa trazer `Uniqueid` ou
`DestUniqueid` exatamente igual ao `channel_id` persistido.
Um `AttemptID` explícito e idêntico só é aceito como compatibilidade
para eventos sem identificadores de canal. Se há identificador de canal
divergente, a tentativa é rejeitada, mesmo que `AttemptID` coincida.
A validação continua exigindo tenant confiável e número correspondente.

Eventos `OriginateResponse` com `Failure` são anotados mas não
liberam rediscagem automática. Estados sem prova são mantidos em
`discando`, para o fluxo de revisão manual auditado pelo Manual 119.

## Limitações e riscos a homologar

- `DialEnd` nem sempre acontece na mesma perna de canal criada pela
  ação `Originate`. Quando o `ChannelId` está só na primeira perna
  e não há `Uniqueid` correspondente, o sistema **não presume**
  conclusão. Uma evolução posterior pode correlacionar eventos
  `DialBegin`, `DialEnd` e `Linkedid` com provas bidirecionais.
- `OriginateResponse` com `ActionID` e `Uniqueid` é documentado nas
  versões recentes do Asterisk; versões antigas podem omitir campos.
  A API falha de maneira conservadora nesses casos.
- O mesmo telefone em duas campanhas ou em campanha e callback não
  deve provocar atualização cruzada. A identidade exata do canal evita
  a colisão; se faltar, nenhum registro é marcado como concluído.
- A travagem multi-processo depende do mesmo volume com `flock`
  (Manual 119), e o AMI de leitor único é detalhado no Manual 121.

## Testes direcionados

```bash
cd queue-api
python3 -m pytest -q tests/test_outbound_channel_correlation.py \
  tests/test_outbound_attempt_fencing.py \
  tests/test_campaign_tenant_http.py
```

Testar ainda em Asterisk real a correspondência do `ChannelId` entre
`OriginateResponse.Uniqueid` e `DialEnd.Uniqueid` (ou `DestUniqueid`)
para discagem de campanhas **e** callbacks; sem tal evidência não há GO
operacional das alterações desta PR.

PR baseada na #75, sem merge, deploy ou homologação declarada.
