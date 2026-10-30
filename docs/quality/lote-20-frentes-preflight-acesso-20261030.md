# AXE PABX — 20 controles de pré-voo: identidade, filas e gravações

**Data:** 30/10/2026  
**Status:** `CODE_REGISTERED_PENDING_REAL_HOMOLOGATION`  
**Alcance:** 20 verificações técnicas de **arquivos privados do ambiente em que o utilitário é executado**. Não são 20 novas funcionalidades de telefonia, nem substituem o gate de 13 cenários reais em `scripts/homologation_gate.py`.

## O que foi entregue

Novo utilitário somente leitura `queue-api/operational_access_preflight.py`, que inspeciona dois arquivos de acesso privados: **credenciais de filas** (`queue_access.json`) e **ACL de gravações** (`recording_access.json`), sem imprimir tokens, hashes, números, clientes, caminhos, gravações ou metadados individuais.

Ele retorna, para cada controle, três estados: `pass` (condição mecânica satisfeita), `fail` (condição não satisfeita), ou `unknown` (ausência de dado ou dependência inválida). `unknown` bloqueia a prontidão para revisão tanto quanto `fail`. A saída conserva `operational_go_authorized=false` e `operational_homologation_claimed=false` em qualquer cenário.

## Controles implementados

| ID | Critério |
|---|---|
| AC-01 | Arquivo de credenciais de filas é regular e privado |
| AC-02 | Esquema de credenciais de filas validado pelo loader seguro |
| AC-03 | Catálogo de credenciais de filas não está vazio |
| AC-04 | Há ao menos um token não expirado para filas |
| AC-05 | Há um supervisor ou administrador com token não expirado para filas |
| AC-06 | Não há tokens expirados retidos no catálogo de filas |
| AC-07 | Nenhum token ativo possui **validade restante** maior que 24h |
| AC-08 | Nenhum token ativo está a cinco minutos ou menos de expirar |
| AC-09 | Pickup sintético de outro tenant é negado |
| AC-10 | Autenticação de filas sem Bearer é negada |
| RC-01 | Arquivo de ACL de gravações é regular e privado |
| RC-02 | Catálogo de gravações validado pelo loader seguro |
| RC-03 | Há ao menos um token ativo para gravações |
| RC-04 | Não há tokens expirados retidos no catálogo de gravações |
| RC-05 | Nenhum token de gravações ativo possui validade restante maior que 24h |
| RC-06 | Há ao menos uma gravação classificada no catálogo |
| RC-07 | Cada gravação catalogada possui referência técnica de origem (`source_ref`) |
| RC-08 | Propriedade declarada de gravações respeita seu tenant |
| RC-09 | Administrador sintético de empresa estrangeira não lê gravação do outro tenant |
| RC-10 | Agente sintético não proprietário não lê gravação do catálogo |

Critérios de validade restante e proximidade de expiração são **recomendações conservadoras** para revisão, não obrigações legais. Não inferem o TTL original de cada credencial. Catálogos legados sem `source_ref` são sinalizados: isso significa prova de origem não registrada no catálogo, não prova de vazamento.

## Execução em host autorizado

```bash
python3 queue-api/operational_access_preflight.py \
  --queue-policy /app/data/queue_access.json \
  --recordings-policy /app/data/recording_access.json
```

Os caminhos acima são exemplos de volumes privados da API. É necessário executá-lo em ambiente autorizado **onde esses dois arquivos realmente existam**. Arquivos não são criados nem alterados. Códigos de saída: `0` quando os 20 controles passam, `1` quando há falha ou dado insuficiente, `2` quando há erro de invocação. Mesmo o código `0` indica **somente prontidão para revisão de segurança do catálogo**, não GO em produção.

## Limites e segurança

- Os controles AC-09, AC-10, RC-09 e RC-10 executam **chamadas de funções de autorização com identidades sintéticas em memória**. **Não são testes HTTP, chamadas SIP, chamadas reais ou verificação de gravação de áudio**.
- Abertura dos catálogos reutiliza loaders existentes com proteção de arquivo privado, sem seguir symlinks. O controle de permissões complementa o loader, mas não prova gestão de credenciais de toda a infraestrutura.
- O utilitário não verifica identidade compartilhada SSO, revogação entre serviços, sessão do painel admin, certificados, tráfego real, fonte CDR/MixMonitor, backup/restauração, failover, simultaneidade ou disponibilidade.
- Não expõe valores do token nem seu SHA-256, nomes de arquivos, ramais ou proveniência de gravações; reporta apenas estado e descrição fixa dos controles.
- A cobertura dos novos testes usa arquivos temporários e dados sintéticos, inclusive t1/t10, ACL inválida, permissões inseguras, expiração, origem ausente e entrada corrompida.
- A CI do repositório precisa aprovar integralmente esta PR antes do merge. Nenhum deploy/homologação de campo é executado.
- O projeto formal permanece em **7/16 marcos (43,8%)**, com **15 provas operacionais pendentes** da issue #173. **Produção NO-GO** e `operational_go_authorized=false`.

**Arquivos:** `queue-api/operational_access_preflight.py`, `queue-api/tests/test_operational_access_preflight.py`, este documento.
