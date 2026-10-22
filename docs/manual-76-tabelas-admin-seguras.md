# Manual 76 — Renderização segura no painel de administração

## Objetivo

Evitar que valores vindos das APIs sejam interpretados como HTML dentro
das tabelas administrativas do AXE PABX. Antes, algumas listas montavam
`innerHTML` com nomes e outros campos diretamente interpolados, o
que poderia permitir execução de conteúdo inesperado em um navegador
autenticado se informações maliciosas chegassem ao cadastro.

## Alterações

As seguintes listas foram convertidas para criação explícita de elementos
`tr`, `td` e `button`, usando `textContent` e `setAttribute`:

- Ramais: nome técnico, nome de exibição, número, editar e excluir.
- Lista de bloqueio: número, desbloquear.
- Clientes VIP: número, ramal destino, remover.
- Usuários administrativos: username, papel, editar e excluir.

Os botões continuam associados diretamente às ações existentes pelos
seus próprios listeners. A tabela e a revisão de tenants já haviam
recebido tratamento semelhante no Manual 72.

## Verificação automatizada

```bash
python3 -m pytest -q tests/test_admin_html.py
node --test tests/ui_browser.test.cjs
```

A suíte de navegador injeta uma sequência HTML com `img/onerror`
na resposta simulada das quatro APIs e verifica que o texto aparece,
nenhum elemento `img` é criado nessas tabelas, o código malicioso
não é executado e as ações dos botões permanecem disponíveis.
Não há chamada SIP nem alteração de ambiente real nesse teste.

## Homologação funcional

1. Entrar no painel como administrador e abrir cada seção.
2. Conferir tabelas com dados normais, vazias e com acentuação.
3. Editar um ramal e validar o preenchimento dos campos.
4. Verificar ações de exclusão e remoção apenas em dados de teste.
5. Confirmar que a permissão de supervisor permanece restrita.

## Limitações

A correção protege essas **quatro tabelas**. Outros pontos que usem
HTML construído dinamicamente, integrações externas ou bibliotecas
de terceiros exigem auditoria própria. A segurança do frontend deve
ser combinada com validação de backend, autenticação, TLS e uma
política CSP adequada para produção.
