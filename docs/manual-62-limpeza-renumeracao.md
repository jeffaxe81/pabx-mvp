# Manual 62 — Limpeza de mapeamento ao renumerar ramal (item #62)

## O que fecha
O manual 55 (monitoramento de ramais dinâmicos) documentou
explicitamente como limitação: **"se o número do ramal mudar numa
edição, o mapeamento do número antigo não é limpo automaticamente —
só o novo é registrado"**. Este item fecha essa lacuna.

## O problema que existia
Editar um ramal pra trocar o número (ex: `1150` → `1160`) registrava
o mapeamento novo (`1160 → vendas-1`) mas deixava o antigo
(`1150 → vendas-1`) órfão no AstDB — apontando pra um ramal que já
não existe mais com aquele número. Tecnicamente inofensivo (o
`ChanSpy` simplesmente não encontraria canal nenhum ativo pra
espionar), mas um mapeamento incorreto sobrando no banco de dados.

## A correção
`_handle_update_extension` agora **captura o registro antigo antes de
atualizar** — mesma técnica já usada em `_handle_delete_extension`
(manual 55), porque `update_extension()` também não devolve o estado
anterior. Se o número **ou** o tenant mudou, desregistra o
mapeamento antigo antes de registrar o novo — os dois na mesma
conexão AMI.

```
Captura o registro ATUAL (antes de qualquer mudança)
  ↓
Atualiza o ramal de verdade
  ↓
Número ou tenant mudou? → desregistra o mapeamento ANTIGO
  ↓
Sempre registra o mapeamento NOVO
```

Editar um ramal **sem** mudar número/tenant (ex: só o nome de
exibição ou a senha) não desregistra nada — só faz sentido limpar o
antigo quando ele de fato mudou.

## `regenerate_and_reload` ganhou suporte a múltiplas ações
Antes, a função só aceitava **uma** ação AMI extra
(`extra_ami_action`, singular) — suficiente pra criar/remover um
ramal, mas não pra renumerar (que precisa de duas: desregistrar +
registrar). Generalizado pra `extra_ami_actions` (lista), executadas
em sequência na mesma conexão.

## Como testar manualmente
1. Crie um ramal dinâmico (ex: número `1150`, nome `vendas-1`)
2. Edite esse ramal, trocando o número pra `1160`
3. Tente monitorar `*811150` (o número antigo) — confirme que cai em
   "destino inválido" (o mapeamento foi limpo)
4. Tente monitorar `*811160` (o número novo) — confirme que funciona

## Teste automatizado
- `admin-api/tests/test_server_security.py` (2 testes novos) —
  captura do registro anterior acontece antes do `update_extension()`
  de verdade, desregistro só acontece quando número ou tenant mudou
- **893 testes no total**, em 8 suítes

## Um problema de edição encontrado e corrigido durante este trabalho
Ao escrever os testes, um `str_replace` acabou apagando por engano a
assinatura de uma função de teste já existente (o texto de busca
incluía, sem querer, o início da função seguinte). Percebido
imediatamente ao rodar a suíte — a contagem de testes mudou de forma
inesperada — e corrigido reconstruindo as duas funções separadamente
antes de seguir. Fica registrado aqui como lembrete de que rodar a
suíte depois de cada edição (não só no final) é o que permite pegar
esse tipo de erro na hora, não depois.

## Limitações conhecidas (honestidade técnica)
- **Só cobre criação/edição/remoção pelo painel** — se alguém editar
  `extensions_store.json` diretamente por fora da API (não deveria,
  mas tecnicamente possível), o mapeamento não seria sincronizado
- **Nunca testado contra um Asterisk real** — mesma situação de
  sempre pro resto das integrações AMI/AstDB deste projeto
