# Manual 112 — Acesso ao correio de voz por identidade SIP autenticada

## Risco que motivou o ajuste
O atalho telefônico *97 escolhia a caixa postal usando o
`CALLERID(num)`, que pode ser informado pelo originador da chamada.
Isso não é prova de identidade: um usuário poderia fornecer outro
Caller ID e selecionar uma caixa diferente dentro do mesmo tenant.
O PIN do correio de voz ainda existia, mas não deve ser a única barreira.

## Proteção implementada
Tanto em `asterisk/extensions.conf` (t1/t2) quanto em
`admin-api/tenants.py` (t3+ gerados pelo wizard), o *97:
1. Obtém `CHANNEL(endpoint)`, isto é, o nome do endpoint PJSIP
   associado ao canal autenticado, em vez de confiar no Caller ID;
2. Nega o acesso caso o endpoint não esteja disponível;
3. Confirma `PJSIP_ENDPOINT(endpoint,context)` no contexto interno
   **exato** daquele tenant;
4. Confirma `PJSIP_ENDPOINT(endpoint,mailboxes)` igual ao único
   mailbox `endpoint@tenant` esperado;
5. Só então chama `VoiceMailMain(endpoint@tenant)`; em todas as
   negativas, encerra com `Hangup(21)`.

Não existe fallback para mailbox fornecido pelo originador da chamada
ou salto para outra empresa. A checagem de correspondência exata evita
a confusão entre `t1` e `t10`.

## Compatibilidade
Os ramais gerenciados que tenham nome sem prefixo `tN-` continuam
potencialmente compatíveis, desde que o endpoint esteja associado
ao contexto do tenant e tenha `mailboxes=nome@tenant`, como o
gerador atual produz. Chamadas não originadas por PJSIP autenticado
não podem utilizar o atalho *97.

Esta mudança não altera o fluxo de depósito de mensagens
(`VoiceMail()`), o PIN cadastrado, o armazenamento de áudio ou as
permissões administrativas. Os PINs legados `1234` dos exemplos
estáticos t1/t2 e contas migradas exigem rotação antes de produção:
**esta entrega não elimina o risco de PIN fraco**.

## Validação estática
```bash
cd admin-api
python3 -m pytest -q tests/test_voicemail_authenticated_endpoint.py
```

Os testes verificam t1/t2 e os templates t3/t4/t10/t25, incluindo
mutações que tentam reintroduzir Caller ID, trocar contexto/mailbox,
eliminar guardas ou antecipar o VoiceMailMain.

## Limites de homologação
Este incremento comprova o contrato de configuração. Ainda faltam
provas funcionais em Asterisk real com *97, PIN válido/inválido,
tentativa de Caller ID falsificado, caixa de outra empresa e ramais
legados. O marco 8 continua aberto e não autoriza implantação ou GO.
