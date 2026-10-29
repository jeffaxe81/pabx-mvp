# Manual 131 — SIP efêmero do laboratório versus mailbox de fallback

## Diagnóstico

O wizard de tenants dinâmicos provisiona a caixa `t3-1001@t3` para
recebimento de mensagens de fallback. Ela **não** implica um ramal SIP
`t3-1001` implantado em produção.

O laboratório de chamadas, entretanto, cria deliberadamente um ramal
PJSIP `t3-1001` temporário via `prepare_calls()`. Usa credencial SIP
aleatória e configuração gerada em staging descartável. Isso é necessário
porque o cliente de teste `CallPeer` usa SIP/TLS + SDES-SRTP, enquanto
`t3-recepcao` é WebRTC com DTLS-SRTP.

## Comportamento e regressão

- A suíte SIP real de `*97` mantém os endpoints de laboratório
  `t1-1001`, `t2-1001`, `t3-1001`.
- A execução `--calls --voicemail` requer `prepare_calls()`;
  se o endpoint de laboratório não tiver credencial, falha de maneira
  explícita antes de originar.
- Novo teste prova que `prepare()` sozinho **não** cria credencial
  SIP para `t3-1001`, mesmo criando sua caixa de mensagens, e que
  `prepare_calls()` cria o peer SIP apenas no staging isolado.
- O teste do ramal real do navegador permanece no job WebRTC;
  ele não pode ser substituído por uma prova de SDES-SRTP.

## Como executar

```bash
python3 -m pytest -q scripts/tests/test_voicemail_pin_bootstrap_lab.py
python3 -m lab.asterisk_lab --calls --voicemail --voicemail-dtmf \
  --report lab-results/voicemail.json
```

## Limites de homologação

Provar rota, mídia DTMF e presença de mailbox não comprova PIN
válido/inválido, bloqueio após tentativas, leitura negada entre empresas
ou isolamento do spool. Essas provas continuam pendentes na issue #88.
O Marco 8 permanece em andamento. Não há liberação para produção.
