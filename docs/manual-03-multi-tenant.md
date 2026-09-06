# Manual 03 — Multi-tenant

## O que é
Isolamento lógico entre "empresas" (tenants) no mesmo Asterisk: cada
uma tem seus próprios ramais, dialplan e caixas de voz, sem enxergar
nem conseguir discar para a outra — mesmo que a numeração de ramal se
repita entre elas.

## Como configurar
Cada tenant tem um prefixo (`t1-`, `t2-`, ...) usado em três lugares:
1. **`pjsip.conf`**: nome do endpoint (`t1-1001`) e `context=t1-internal`
2. **`extensions.conf`**: um contexto próprio (`[t1-internal]`) com o
   dialplan daquele tenant, e um contexto de hints próprio
   (`[t1-hints]`)
3. **`voicemail.conf`**: uma seção própria (`[t1]`) com as caixas de
   voz daquele tenant

Para criar um tenant 3, duplique os três pontos acima trocando o
prefixo para `t3-`.

## Como testar manualmente
1. Registre um softphone como ramal do tenant 1 (ex: `t1-1001`)
2. Registre outro como ramal do tenant 2 (ex: `t2-1001`) — repare que
   o número de discagem é o mesmo (`1001`) nos dois
3. Do ramal do tenant 1, tente discar `1001` — deve tocar no *outro*
   ramal do tenant 1 (`t1-1002`), nunca no do tenant 2
4. Confirme que não existe nenhuma forma de um tenant discar direto
   para o número interno do outro

## Teste automatizado
`tests/test_extensions_conf.py::test_tenants_do_not_share_extension_numbers_in_same_context`
`tests/test_extensions_conf.py::test_expected_contexts_present`

## Limitações conhecidas
- Isolamento é **lógico**, não há billing nem painel separado por
  tenant — é o mesmo Asterisk, mesmo dialplan engine, mesmos arquivos
  `.conf` editados manualmente
- Para isolamento mais forte (cada tenant com seu próprio painel,
  faturamento, limites de uso), o caminho é uma camada de API/banco de
  dados controlando o Asterisk via AMI/ARI — ver backlog #10 no prompt
  master (painel de administração web)
