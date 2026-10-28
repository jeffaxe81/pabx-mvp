# Manual 129 — Marco 8: matriz HTTP de isolamento multiempresa

## Avanço nesta etapa

O teste `queue-api/tests/test_multi_tenant_cross_service_http.py` executa a
mesma `server.Handler` de produção em **loopback**, mas com dados
temporários e nenhuma conexão ao Asterisk. Exercita no **mesmo servidor**
as políticas independentes de filas e gravações.

Empresas de ensaio: `t1`, `t2` e `t10` (evita engano de prefixo).
Todas usam tokens distintos por serviço, com hashes persistidos em
catálogos de teste e nunca em variáveis de produção.

## Critérios cobertos

- Um token vê somente os canais de sua fila, mesmo pedindo outro tenant
  em `?tenant=`.
- Um token de gravações vê e baixa apenas arquivos da sua empresa,
  independentemente do nome solicitado. Tentativas cruzadas são 404.
- Tokens de filas não entram em gravações e vice-versa (401).
- Nenhum pedido de pickup entre empresas chega à interface AMI.
- Origem CORS inesperada é rejeitada nas duas superfícies.
- Revogação de um token de gravações passa a valer sem reiniciar a API
  e não revoga as credenciais de outra empresa.

Execute:

```bash
cd queue-api
python3 -m pytest -q tests/test_multi_tenant_cross_service_http.py
```

A suíte roda também no job `pytest | queue-api` da CI estática.
Nenhum dado de cliente, credencial real ou chamada telefônica é usado.

## Panorama do marco 8

| Domínio | Evidência já existente | Falta para aceite integral |
|---|---|---|
| SIP/Ramais | Negativas reais, observador sem INVITE e CDR | Revisar ambiente-alvo e regras de infraestrutura |
| DIDs | Entradas reais, roteamento por tenant, desconhecidos rejeitados | Integração com demais recursos e ambiente-alvo |
| Voicemail | Roteamento *97 real por endpoint autenticado | Negativas de PIN e acesso às mensagens de outro tenant |
| Filas | ACLs HTTP reais e dialplan com âncora de tenant | Validar filas em execução no Asterisk junto à API |
| Gravações | Catálogo/ACL e HTTP real em arquivos de teste | Prova integrada de volumes, origem de arquivos e acesso cruzado |

O programa de **16 marcos permanece em 7/16 (43,8%)** até que
todos os critérios do marco 8 tenham evidência suficiente.
`status=in_progress` não autoriza marcar o marco como `done`.

## Limite de homologação

Este teste não representa pentest, separação física de volumes, sessão
SSO, SIP real, acesso a mailboxes, URA ou prova de operação em
infraestrutura de cliente. A homologação geral e o GO permanecem
bloqueados. Concluir o marco 8 só após evidências reais dos cinco
domínios e revisão do responsável técnico.
