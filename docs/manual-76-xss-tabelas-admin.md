# Manual 76 — Proteção contra HTML injetado no painel administrativo

## Contexto

Nomes de ramal e outros campos retornados pelas APIs do painel não
devem ser colocados diretamente no código HTML. A interpolação de
texto não confiável em `innerHTML` poderia executar elementos ou
handlers maliciosos na sessão autenticada do administrador.

## Implementação

As quatro listas do painel passam a usar `document.createElement`,
`textContent`, `setAttribute` para atributos de dados e
`addEventListener` para as ações:

- Ramais: nome interno, nome de exibição, número, Editar e Excluir.
- Lista de bloqueios: número e Desbloquear.
- Clientes VIP: número, destino e Remover.
- Usuários: nome, papel, Editar e Excluir.

O wizard de tenants já usava renderização segura desde o Manual 72.
Agora as listas restantes também evitam interpretar os campos
exibidos como marcação HTML.

## Testes

```bash
python3 -m pytest -q tests/test_admin_html.py
node --test tests/ui_browser.test.cjs
```

A regressão de navegador injeta uma string com `<img onerror=...>`
em respostas simuladas para as quatro APIs, confirma que a interface
mostra o valor como **texto**, que nenhum elemento `img` é criado
e que o código inserido não é executado. Não usa clientes reais.

## Operação

A correção não altera banco de dados, credenciais, permissões ou SIP.
Antes de implantar, homologar operações Editar, Excluir, Bloquear,
Desbloquear e Remover VIP em ambiente de teste, tanto para
administrador quanto para supervisor, além do comportamento mobile.

## Limitações

O recurso protege os quatro pontos de renderização citados. Não é
uma auditoria completa contra XSS de toda a aplicação: novos
componentes devem continuar usando DOM/texto e controles de
segurança no servidor, além de CSP e validação de entrada.
