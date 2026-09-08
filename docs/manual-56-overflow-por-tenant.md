# Manual 56 — Overflow entre filas configurável por tenant (item #56)

## O que fecha
O manual 45 (overflow entre filas) documentou explicitamente como
limitação: **"sem interface no painel pra ajustar o valor — precisa
editar `extensions.conf` na mão e recarregar o dialplan"**. Este item
fecha essa lacuna.

## Como funciona
Cada tenant pode configurar o próprio tempo de overflow (em segundos)
pelo painel — sem precisar editar arquivo nenhum. Guardado no AstDB,
mesma família `config-{tenant}` já usada pelo modo feriado (manual
23), chave `overflow-timeout-segundos`.

```
Tenant configurou algo? → usa o valor configurado
Tenant não configurou nada? → cai no OVERFLOW_TIMEOUT_SECONDS global (45s)
```

## Uma diferença técnica importante: `DBGet` vs `DBGetTree`
O modo feriado só precisa responder "sim ou não" — `get_holiday_mode()`
usa `DBGet` e checa se a resposta foi `Success`, sem se importar com
o valor de verdade. Aqui precisamos do **valor numérico** — `DBGet`
sozinho não devolve isso na resposta imediata (o valor vem num evento
assíncrono separado, que a implementação simplificada deste projeto
não capturava). A solução: `get_overflow_timeout()` usa a mesma
técnica já estabelecida em `list_blocked_numbers`/`list_vips`
(`DBGetTree` + leitura em loop com timeout), filtrando pela chave
específica.

## Onde configurar
Painel → seção "Overflow entre filas", logo abaixo do modo feriado.
Aceita de 5 a 600 segundos. O campo já vem preenchido com o valor **em
vigor** pro tenant selecionado (configurado ou o padrão global,
mostrado igual nos dois casos — a interface não distingue "configurado
= 45" de "não configurado, caiu no padrão de 45").

## Como testar manualmente
1. `docker compose up -d`
2. No painel, configure o tenant 1 pra 15 segundos
3. Simule uma chamada que force o overflow (fila de idioma sem
   resposta) — confirme que transborda em ~15s, não nos 45s padrão
4. Troque pro tenant 2 no seletor — confirme que mostra o valor
   próprio dele (ainda 45, já que não foi configurado)

## Teste automatizado
- `admin-api/tests/test_overflow.py` (8 testes) — validação (5-600s,
  aceita string numérica, rejeita não-numérico, rejeita fora do
  limite)
- `admin-api/tests/test_server_security.py` (3 testes novos) —
  admin+supervisor (mesmo papel do modo feriado), validado antes de
  escrever no AstDB, fallback pro padrão quando não configurado
- `tests/test_extensions_conf.py::test_overflow_timeout_configurable_per_tenant_with_global_fallback`
- `admin-api/tests/test_tenants.py::test_render_extensions_overflow_timeout_configurable_per_tenant`
  — tenant novo criado pelo wizard já nasce com essa flexibilidade
- `tests/test_admin_html.py` (3 testes novos) — carregado ao entrar/
  trocar de tenant, envia o tenant certo, converte o valor do input
  (string) pra número antes de enviar
- **849 testes no total**, em 8 suítes

## Limitações conhecidas (honestidade técnica)
- **Um valor por tenant, não por fila individual** — a fila de vendas
  e a de suporte do mesmo tenant usam o mesmo timeout
- **A interface não distingue "configurado igual ao padrão" de "nunca
  configurado"** — mostra o mesmo número nos dois casos, já que o
  valor *em vigor* é idêntico de qualquer forma
- **Nunca testado contra um Asterisk real** — mesma situação de
  sempre pro resto das integrações AMI/AstDB deste projeto
