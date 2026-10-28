# Bloqueio de PIN padrão no gerador de ramais (issue #88)

As caixas estáticas receberam placeholders individuais na PR #89. A
admin-api também precisa preservar essa garantia. Antes desta
correção, `render_voicemail_dynamic` publicava silenciosamente PIN
`1234` para ramais legados sem campo `voicemail_pin`, e uma edição
de cadastro sem PIN persistido reproduzia esse valor.

## Comportamento novo

- Novos ramais continuam recebendo PIN aleatório de oito dígitos,
  gerado e persistido pelo servidor.
- Atualizações de ramal existente preservam seu PIN individual.
- Cadastro legado sem PIN, com `1234` ou com PIN inválido **não é
  regravado automaticamente**. A API nega a operação, orientando
  migração segura por administrador autorizado.
- `render_all` recusa publicar novos .conf quando qualquer ramal
  ainda tem PIN sem migração; impede substituir uma configuração
  existente por credencial conhecida.
- A mudança não altera secretamente um PIN já instalado nem
  modifica caixas de mensagens existentes.

## Pendência operacional

É necessário elaborar e homologar procedimento de rotação de PIN
legado sob autorização, com backup, atualização transacional,
comunicação segura ao titular e validação de voicemail real antes do
GO. Dados existentes com PIN fraco continuarão bloqueando o
reprocessamento até a rotação explícita.

Nenhuma homologação de ambiente real ou liberação de produção.
