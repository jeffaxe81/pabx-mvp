# Manual 55 — Monitoramento de ramais dinâmicos (item #55)

## O que fecha
O manual 42 (monitoramento de chamada) documentou explicitamente
como limitação: **"só cobre as telefonistas (1010/1011) — ramais
dinâmicos criados pelo painel não têm mapeamento automático pro
`ChanSpy` ainda"**. Este item fecha essa lacuna.

## Como funciona
O `admin-api` agora mantém, no AstDB, um mapeamento **número de
ramal → nome do endpoint real** por tenant (família
`extension-map-{tenant}`), sincronizado automaticamente:
- **Criar ramal**: registra o mapeamento
- **Editar ramal**: re-registra (sobrescreve)
- **Remover ramal**: desregistra

O dialplan (`[chamada-monitorada]`) continua tratando `1010`/`1011`
como atalhos fixos (telefonistas), mas qualquer **outro** número
agora consulta esse mapeamento via `${DB(extension-map-${TENANT}/${MONITOR_TARGET})}`
— se o ramal existir, o `ChanSpy` alcança ele; se não existir, cai no
mesmo comportamento seguro de sempre (`destino-invalido`, sem tentar
espionar canal nenhum).

## Reaproveitando a conexão AMI já aberta
`regenerate_and_reload()` (que já conectava no AMI pra recarregar o
Asterisk depois de qualquer mudança de ramal) ganhou um parâmetro
opcional `extra_ami_action` — a sincronização do mapeamento roda na
**mesma conexão**, em vez de abrir uma conexão AMI extra só pra isso.

## Uma limitação técnica na remoção
`delete_extension()` do `store.py` nunca devolveu o registro apagado
— só confirma que apagou. Pra desregistrar o mapeamento corretamente,
o `admin-api` precisa **consultar o ramal antes de apagar** (captura
número/tenant primeiro, só depois chama a remoção de verdade). Isso é
testado explicitamente
(`test_deleting_extension_captures_record_before_removal_to_unregister_mapping`).

## Como testar manualmente
1. Crie um ramal dinâmico pelo painel (ex: número `1150`, nome
   `vendas-1`)
2. Coloque esse ramal numa chamada
3. De outro ramal, disque `*811150` (escuta silenciosa) — confirme
   que consegue monitorar, mesmo esse ramal nunca tendo sido
   "telefonista"
4. Remova o ramal `vendas-1` pelo painel
5. Tente monitorar `1150` de novo — confirme que cai em
   "destino inválido" (o mapeamento foi limpo)

## Teste automatizado
- `admin-api/ami_client.py`: `register_extension_mapping`/
  `unregister_extension_mapping` (novos métodos, mesmo padrão do
  resto das integrações AstDB do projeto)
- `admin-api/tests/test_server_security.py` (4 testes novos) —
  criação e edição registram o mapeamento, remoção captura o registro
  ANTES de apagar (ordem certa: captura → apaga → desregistra)
- `tests/test_extensions_conf.py::test_monitoring_falls_back_to_astdb_lookup_for_dynamic_extensions`
- **833 testes no total**, em 8 suítes

## Limitações conhecidas (honestidade técnica)
- **Se o número do ramal mudar numa edição**, o mapeamento do número
  **antigo** não é limpo automaticamente — só o novo é registrado.
  Ficaria um mapeamento órfão apontando pro mesmo endpoint com o
  número velho, até alguém sobrescrever manualmente ou remover o
  ramal por completo
- **Sem sincronização retroativa** — ramais que já existiam antes
  desta mudança só ganham o mapeamento na próxima vez que forem
  editados (não há um comando pra "sincronizar tudo de uma vez" ainda)
- **Nunca testado contra um Asterisk real** — mesma situação de
  sempre pro resto das integrações AMI/AstDB deste projeto
