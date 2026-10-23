# Manual 82 — Ramais dinâmicos em tenants t3+

## Escopo

O painel administrativo aceitava ramais apenas nos tenants fixos
`t1` e `t2`, apesar de o wizard já criar `t3`, `t4` e seguintes.
Os contextos do Asterisk gerados pelo wizard faziam `#include`
de três arquivos por tenant, mas o gerador de ramais não os criava.

Esta entrega conecta os fluxos e mantém o isolamento.

## Funcionamento

1. O backend lê o catálogo `tenants.json` do wizard, preservando
   `t1/t2`, e recusa registros com IDs inválidos ou duplicados.
2. POST e PUT de ramais recebem uma lista explícita dos tenants
   provisionados. Apenas passar `tenant: t3` na requisição sem
   cadastro correspondente não autoriza a criação.
3. O gerador passa a produzir `extensions_dynamic_dial-t3.conf`,
   `extensions_dynamic_hints-t3.conf` e
   `voicemail_dynamic_t3.conf` (e equivalentes para outros IDs
   provisionados), sem misturar ramais entre contextos.
4. Um tenant novo recebe esses três arquivos inicialmente vazios
   **antes** do reload do Asterisk, para que os `#include` não
   apontem para arquivos ausentes.
5. Um ramal de `t3` usa `context=t3-internal`,
   `subscribe_context=t3-hints` e `mailboxes=<ramal>@t3`.
6. O painel consulta `GET /api/tenant-options` com Bearer para
   montar o seletor. A resposta é permitida a administrador e
   supervisor, contendo apenas ID e nome, **sem expor DID**.
   Valores de exibição são inseridos via `textContent`, sem HTML.
7. Ao adicionar ou excluir empresa, as opções do seletor são
   atualizadas; um tenant removido não permanece selecionado.
8. Na exclusão de tenant, o PJSIP compartilhado é regenerado sem os
   endpoints apagados antes do reload, para não conservar credenciais
   SIP órfãs de empresas removidas.

## Testes

```bash
(cd admin-api && python3 -m pytest -q tests/test_store.py tests/test_conf_generator.py tests/test_server_security.py)
python3 -m pytest -q tests/test_admin_html.py
node --test tests/ui_browser.test.cjs
```

Testes verificam que ramais em `t3` aparecem somente nos arquivos
desse tenant, que o catálogo bloqueia IDs desconhecidos, que os
arquivos vazios são gerados e que a seleção `t3` funciona com
API simulada e nomes contendo HTML hostil.

## Homologação com Asterisk

Em laboratório, criar o tenant `t3` pelo wizard e conferir os
cinco arquivos da empresa mais os três includes vazios. Depois:

- Criar o ramal `1115` em `t3` e registrar seu endpoint SIP.
- Verificar `dialplan show t3-internal` e
  `pjsip show endpoint <nome-do-ramal>`.
- Realizar uma chamada interna dentro de `t3` e conferir o
  voicemail no contexto correto.
- Repetir o número `1115` em `t1` com endpoint de outro nome e
  comprovar que chamadas/gravações/caixas não se cruzam.
- Remover somente o tenant de teste e verificar limpeza dos seus
  arquivos, ramais e mapeamentos AstDB.

**Limites:** não há implantação ou chamada real nesta entrega.
O código não resolve transações/rollback distribuídos entre JSON,
arquivos e AMI, nem fornece mecanismo automático de migração
para tenants com estado legado inconsistente. O GO requer a
matriz de evidências do Manual 73.
