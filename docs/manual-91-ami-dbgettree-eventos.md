# Manual 91 — Leitura completa de listas AstDB pelo AMI

## Problema

As consultas administrativas `DBGetTree` de VIPs, bloqueios e timeout
de transbordo enviavam a ação pelo socket e liam até um timeout de dois
segundos, sem esperar o evento de conclusão. O último comando
`settimeout(None)` também podia deixar a conexão sem limite de espera
nas ações seguintes. Eventos de outras consultas podiam se misturar
à listagem.

## Implementação

O cliente AMI passa a usar o mesmo buffer de framing do Manual 90
para receber listas do AstDB:

- Exige uma resposta inicial `Response: Success` com `ActionID`
  correspondente à ação solicitada.
- Lê os eventos `DBGetTreeResponse` (com compatibilidade com
  `DBGetTreeEntry`) até o evento final `DBGetTreeComplete`.
- Exige associação do evento ao `ActionID` esperado; notificações
  de outras ações são ignoradas em quantidade limitada.
- Aceita exclusivamente chaves prefixadas pela família consultada
  (`vip-tN`, `blocklist-tN`, `config-tN`), sem misturar empresas.
- Limita a consulta a 1.000 entradas e 2.048 eventos recebidos.
- Mantém a trava reentrante durante todo o fluxo para impedir
  interposição de comandos na mesma conexão.
- Mantém o timeout previamente definido da conexão e não dorme
  artificialmente por dois segundos.

## Testes automatizados

```bash
(cd admin-api && python3 -m pytest -q tests/test_ami_dbgettree.py)
```

Os dez testes usam socket simulado, incluindo pacotes fragmentados,
duas respostas em uma leitura, filtro multiempresa, timeout de
transbordo, lista vazia, ausência de evento final, falha de
autorização, evento inesperado e consulta seguinte na mesma sessão.

Referência técnica: [DBGetTree — documentação do Asterisk](https://docs.asterisk.org/Latest_API/API_Documentation/AMI_Actions/DBGetTree/).

## Limites de homologação

**Os testes não se conectam ao Asterisk real.** É necessário confirmar,
em laboratório, os eventos e nomes retornados pela versão utilizada,
a consistência do AstDB após criar/remover bloqueios e VIPs, e
o tratamento de falha de rede durante a consulta. O código não faz
rollback de operações de escrita no AstDB nem transação distribuída.

Siga os Manuais 73, 87 e 90 antes de autorizar o GO operacional.
