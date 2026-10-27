# Manual 108 — Roteamento de filas restrito à empresa

## Proteção implementada (marco 8, parcial)
No início da extensão 1000 de `t1-internal`, `t2-internal` e dos
contextos `tN-internal` produzidos pelo wizard, o dialplan agora:

1. Reatribui `TENANT=tN` pelo contexto interno efetivo, sem herdar
   identidade arbitrária fornecida por uma etapa anterior da chamada.
2. Aceita `FILA_IDIOMA` **somente** se coincidir exatamente com
   `fila-tN-en` ou `fila-tN-es`. Essas filas seguem o fluxo de idiomas.
3. Para qualquer outro valor, inclusive vazio, `fila-t2` em contexto
   `t1`, ou `fila-t10` em contexto `t1`, escolhe a fila padrão
   `fila-tN`. Não há comparação por prefixos.
4. Só então calcula fila de overflow, timeout e accountcode e
   executa `Queue()`. Não se altera a URA ou o desvio por DID.

Assim, o contexto de ramal não permite escolher fila de outra empresa
mesmo que uma variável de canal anterior venha incorreta ou adulterada.

## Regressões
```bash
cd admin-api
python3 -m pytest -q tests/test_tenant_queue_boundary.py
```

Os testes auditam os contextos estáticos t1/t2 e a saída do gerador para
t3/t4/t10/t25, exigindo a sequência e os alvos de salto. Mutações que
retiram âncora de tenant, direcionam idiomas a outra empresa, eliminam
fallback, alteram salto, acrescentam Queue prematura ou reatribuem
TENANT falham. Estes testes são estáticos e **não** executam chamadas.

## Evidências e limites
A prova de execução Asterisk real segue pela CI do laboratório da PR
e pelos marcos de homologação. Não foram comprovados por este incremento
os acessos HTTP/voicemail/gravações ou tentativas SIP cruzadas do marco
8 completo. A lista de verificações em infraestrutura de cliente
permanece necessária antes do GO operacional.
