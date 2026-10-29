# Manual 130 — Correção da caixa de fallback de voicemail por empresa

## Defeito identificado

O dialplan gerado pelo wizard de empresas encaminha chamadas não atendidas
para `VoiceMail(${TENANT}-1001@${TENANT},u)`, mas a configuração inicial
da empresa criava somente `tN-recepcao` e `tN-recepcao-2`.
Assim, o destino de fallback `tN-1001@tN` não tinha mailbox configurada.

## Correção

- O wizard cria **três** caixas de voz por nova empresa: `tN-1001`
  (fallback sem agente), `tN-recepcao` e `tN-recepcao-2`.
- Cada caixa recebe PIN numérico individual, gerado localmente e distinto
  dos demais PINs do mesmo tenant.
- O painel apresenta os três PINs somente na resposta inicial do wizard,
  separadamente das duas credenciais SIP. Não cria ramal SIP `tN-1001`
  nem publica credenciais em listagens comuns.
- O validador do laboratório passa a exigir que `t3-1001` realmente
  exista na configuração temporária antes de iniciar o Asterisk.
- Testes verificam a presença do fallback para `t3` e `t10`,
  ausência de PIN, PIN repetido, PIN inválido e provisionamento recuperável.

## Compatibilidade e migração

A atualização é aplicada a **novos tenants criados pelo wizard**.
Empresas dinâmicas já provisionadas com arquivo de voicemail antigo
não recebem uma nova caixa automaticamente, para evitar sobrescrever
PINs e mensagens existentes. Precisam de migração administrativa
controlada, com backup da configuração, novo PIN individual e reload
de voicemail sob supervisão.

A caixa `tN-1001` funciona como destino de depósito de mensagens do
fallback; não pressupõe a existência de um endpoint SIP `tN-1001`.
Se o cliente exigir acesso interativo, deverá ser definido um fluxo de
recuperação autorizado para essa mailbox.

## Testes

```bash
cd admin-api
python3 -m pytest -q tests/test_tenants.py tests/test_tenant_provisioning.py
```

O teste integrado do laboratório Asterisk continua obrigatório, assim
como os gates estáticos e a regressão da interface.

**Limite:** existência de mailbox e PIN gerado não comprovam ainda a
autenticação DTMF válida/inválida, lockout, acesso a mensagens por
empresa nem segregação física do spool. Issue #88 permanece aberta.
O marco 8 e a liberação operacional também permanecem pendentes.
