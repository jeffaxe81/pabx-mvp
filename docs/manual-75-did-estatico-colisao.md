# Manual 75 — Prevenir conflito de DID na criação multiempresa

## Risco operacional

A plataforma mantinha DIDs explícitos no `asterisk/extensions.conf`,
dentro do contexto `[from-tdm-gateway]`, mas o assistente de tenants
verificava duplicidade somente entre registros criados pelo próprio
wizard. Assim, era possível associar um DID estático do tenant 1 ou 2
a uma nova empresa no AstDB, sem que a chamada chegasse à nova empresa:
a regra fixa do dialplan tem precedência.

## Implementação

No fluxo administrativo de criação de tenant, a API agora:

1. Lê o arquivo de dialplan efetivamente montado em
   `ASTERISK_CONF_DIR/extensions.conf`.
2. Coleta exclusivamente os DIDs numéricos explicitamente definidos
   com prioridade `1` dentro de `[from-tdm-gateway]`.
3. Rejeita a criação quando o DID solicitado coincide com uma das
   rotas fixas.
4. Rejeita a operação quando o arquivo estiver inacessível ou o
   contexto não puder ser identificado. Nenhuma configuração nova
   é escrita nessa condição.
5. Mantém a verificação existente de duplicidade entre tenants
   cadastrados pelo wizard.

Essa proteção é adicional ao comportamento fail-closed de DIDs
desconhecidos (Manual 68).

## Testes

```bash
(cd admin-api && python3 -m pytest -q tests/test_tenants.py tests/test_server_security.py)
```

Casos: números em outros contextos não geram conflito falso;
comentários não são interpretados como rota; DIDs fixos são
identificados; ausência de contexto impede a operação; DID novo é
aceito pelo validador.

## Homologação real

No laboratório, tentar cadastrar `5511900001111` em t3: a API
deve rejeitar, sem criar arquivos, registros AstDB ou senhas. Em
seguida, cadastrar um DID de teste realmente disponível para t3
e comprovar seu roteamento com chamada de teste e isolamento da URA.

## Limitações

O verificador detecta regras exatas com número literal; faixas,
expressões/padrões de discagem, alterações dinâmicas no dialplan já
carregado e mapeamentos externos de operadora/gateway precisam ser
verificados pela equipe na homologação. Esta versão não faz bloqueio
transacional contra duas solicitações simultâneas de criação nem
substitui a auditoria do AstDB existente.
