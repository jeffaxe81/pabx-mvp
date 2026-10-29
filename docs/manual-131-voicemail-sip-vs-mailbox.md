# Manual 131 — Separar identidade SIP de caixa postal no laboratório

## Incidente prevenido

O wizard de tenants dinâmicos gera `t3-1001@t3` como caixa postal de
**depósito** para transbordo; ele **não** cria o endpoint SIP `t3-1001`.
O laboratório de voicemail não pode usar essa mailbox como identidade
de autenticação de um REGISTER SIP.

## Ajuste

- Para `t1` e `t2`, os endpoints SIP de teste seguem `t1-1001` e
  `t2-1001`.
- Para `t3`, o teste SIP/TLS de `*97` autentica **`t3-recepcao`**
  e verifica no canal ativo o argumento
  `VoiceMailMain(t3-recepcao@t3)`.
- A caixa `t3-1001` continua provisionada apenas para receber
  mensagens de fallback; seu PIN é próprio.
- Regressão do `prepare()` confirma que o cliente de laboratório
  possui credenciais para todos os endpoints de teste, mas não para a
  mailbox `t3-1001`, e que as duas mailboxes estão no arquivo do tenant.
  O runtime real continua validando os três tenants.

## Reproduzir

```bash
python3 -m pytest -q scripts/tests/test_voicemail_pin_bootstrap_lab.py
python3 -m lab.asterisk_lab --calls --voicemail --voicemail-dtmf \
  --report lab-results/voicemail.json
```

## Limites

Este teste prova identidade e rota SIP, negociação de DTMF e aplicação
`VoiceMailMain` no canal exato. **Não prova** PIN válido/inválido,
lockout ou leitura cruzada de mensagens reais. A issue #88 permanece
aberta, o marco 8 permanece em andamento e nenhuma liberação para
produção decorre desta correção.
