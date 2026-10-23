# Manual 86 — Limites de JSON nas APIs administrativas

## Objetivo

O painel AXE PABX recebe requisições de criação de ramais, empresas,
usuários e configurações usando JSON. O leitor de corpo anteriormente
aceitava qualquer tamanho declarado no cabeçalho `Content-Length`
e podia lançar exceção com valores inválidos ou JSON de tipo inesperado.

## Proteções acrescentadas

- **Limite de 64 KiB** para o corpo de cada requisição JSON lida pelo
  `admin-api` (constante `MAX_JSON_BODY_BYTES`).
- Rejeição de `Content-Length` negativo, fracionário, não decimal,
  repetido ou maior que o máximo.
- Rejeição de `Transfer-Encoding`: o servidor administrativo usa
  corpos com comprimento explícito e não implementa `chunked`.
- Rejeição de JSON malformado, bytes UTF-8 inválidos, corpo incompleto
  e documentos JSON que não sejam objetos.
- Encerramento da conexão após rejeição, impedindo que bytes restantes
  de um corpo malformado sejam interpretados como outra requisição.
- Compatibilidade preservada para chamadas sem corpo:
  `Content-Length` ausente ou zero ainda produz objeto vazio.

As rotas que já respondiam `400 JSON inválido` continuam usando
esse mesmo contrato. Não há alteração em autenticação nem nos dados
persistidos.

## Verificação

```bash
(cd admin-api && python3 -m pytest -q tests/test_json_body_bounds.py)
```

Os testes cobrem limite exato, excesso sem leitura do conteúdo,
cabeçalhos duplicados, framing `chunked`, caracteres inválidos,
corpo truncado, entrada escalar e caracteres acentuados.

## Pontos de atenção

- Esse limite é aplicado a JSON administrativo. Uploads binários e
  arquivos grandes precisam de endpoint especializado.
- Não há mitigação completa contra conexões muito lentas (slowloris).
  Em produção, aplicar TLS e limites de tempo/corpo adicionais no
  proxy HTTP reverso, mantendo logs sem segredos.
- A validação de conteúdo dos campos continua sendo responsabilidade
  de cada endpoint, mesmo quando o corpo é JSON válido.
- A mudança não representa homologação SIP/RTP, backup, failover ou
  implantação de produção. Consulte o [Manual 73](manual-73-gates-homologacao.md).
