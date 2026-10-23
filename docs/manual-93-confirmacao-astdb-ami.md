# Manual 93 — Confirmação obrigatória de alterações AstDB

## Problema

O cadastro e a remoção de ramais e DIDs executam operações
`DBPut`/`DBDel` via Asterisk Manager Interface (AMI). O cliente
anterior devolvia a resposta AMI ao servidor administrativo, mas as
rotas podiam ignorar um `Response: Error` e continuar o fluxo
como se o mapeamento estivesse sincronizado.

Isso podia resultar em DIDs cadastrados sem roteamento efetivo ou
números de ramal com mapeamento de monitoramento desatualizado.

## Correção

As quatro operações abaixo agora exigem exatamente
`Response: Success`:

- registrar mapeamento número → endpoint SIP;
- remover mapeamento número → endpoint SIP;
- registrar associação DID → tenant;
- remover associação DID → tenant.

Em erro, resposta ausente ou `Follows` inesperado, o cliente lança
uma exceção genérica, sem incluir dados privados de `Message` da
resposta AMI.

Quando a rejeição ocorre em `regenerate_and_reload()`, o
publicador do Manual 87 tenta restaurar os arquivos `.conf` e
recarregar a configuração anterior. O AMI/DB é um sistema separado:
as demais mudanças do procedimento não são revertidas
automaticamente.

## Testes automatizados

```bash
(cd admin-api && python3 -m pytest -q tests/test_ami_db_mutations.py)
```

Os testes verificam respostas `Success`, `Error`, `Follows`
e respostas ausentes nas quatro ações, ausência de vazamento da
mensagem privada e um cenário em que a rejeição do mapeamento
provoca rollback dos arquivos gerados.

## Homologação em laboratório

Registrar e excluir um ramal e um DID de teste com permissões
AMI válidas, confirmando via `database show` que a alteração
foi persistida. Repetir com permissões insuficientes, verificar
erro controlado e analisar o estado do dialplan após compensação.

## Limites

Uma confirmação positiva do AstDB **não comprova** o isolamento,
a configuração completa ou o sucesso de chamadas SIP/RTP. O fluxo
de criação/remoção de tenants ainda precisa de rollback
transacional próprio para JSON, diretórios, AstDB e runtime Asterisk.
As operações de outros subsistemas AMI não foram alteradas nesta PR.

Não houve conexão a servidor real nem homologação operacional.
