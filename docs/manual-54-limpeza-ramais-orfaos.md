# Manual 54 — Limpeza de ramais órfãos ao remover tenant (item #54)

## O que fecha
O manual 52 (remoção de tenant) documentou explicitamente como
limitação: **"ramais dinâmicos criados dentro daquele tenant (pelo
painel, manual 38) não são limpos automaticamente — ficam como lixo
no disco"**. Este item fecha essa lacuna.

## O que mudou
Ao remover um tenant, além dos 5 arquivos de infraestrutura do
wizard (manual 52), agora também são removidos:
1. Os 3 arquivos dinâmicos de ramais criados pelo painel
   (`extensions_dynamic_dial-{tenant}.conf`,
   `extensions_dynamic_hints-{tenant}.conf`,
   `voicemail_dynamic_{tenant}.conf`)
2. Os registros correspondentes no `extensions_store.json`
   (`delete_extensions_by_tenant`) — sem isso, o painel continuaria
   listando ramais de um tenant que não existe mais

A interface agora informa quantos ramais dinâmicos foram limpos
junto (ex: "Tenant 't3' removido e recarregado com sucesso (2
ramal(is) dinâmico(s) também removido(s))").

## Por que isso importa
Antes desta correção, remover um tenant deixava dois tipos de lixo:
- **Arquivos órfãos no disco** apontando pra um contexto
  (`t3-internal`) que não existe mais — inofensivo tecnicamente (o
  Asterisk simplesmente não encontraria o contexto e ignoraria), mas
  sujeira acumulada sem necessidade
- **Dados órfãos no `extensions_store.json`** — esses sim causavam um
  problema real de usabilidade: o painel continuaria mostrando ramais
  "fantasma" de um tenant já removido, confundindo qualquer pessoa
  olhando a lista depois

## Como testar manualmente
1. Crie um tenant de teste pelo wizard (manual 39)
2. Crie um ou dois ramais dinâmicos dentro dele pelo painel (manual 38)
3. Remova o tenant
4. Confirme que a mensagem de resultado menciona quantos ramais foram
   removidos junto
5. Confirme que os 3 arquivos dinâmicos (`extensions_dynamic_dial-*`,
   etc.) sumiram do disco
6. Confirme que os ramais não aparecem mais na lista de ramais do
   painel pra nenhum tenant

## Teste automatizado
- `admin-api/tests/test_store.py` (4 testes novos) —
  `delete_extensions_by_tenant`: remove só do tenant certo, remove
  múltiplos de uma vez, retorna zero quando nada bate, não quebra com
  arquivo de store inexistente
- `admin-api/tests/test_server_security.py::test_remove_tenant_also_cleans_up_dynamic_extensions_and_files`
- `tests/test_admin_html.py::test_remove_tenant_reports_orphaned_extensions_cleaned_up`
- **829 testes no total**, em 8 suítes

## Limitações conhecidas (honestidade técnica)
- **Ainda sem período de graça/soft-delete** — mesma limitação já
  documentada no manual 52, agora estendida também aos ramais
  dinâmicos: a limpeza é imediata e definitiva
- **Nunca testado contra um Asterisk real** — mesma situação de
  sempre; a limpeza de arquivo é uma operação de sistema de arquivos
  simples, mas nunca foi confirmada rodando junto com um reload de
  verdade do Asterisk
